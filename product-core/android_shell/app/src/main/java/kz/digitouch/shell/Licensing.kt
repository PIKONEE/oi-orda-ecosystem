package kz.digitouch.shell

import android.annotation.SuppressLint
import android.content.Context
import android.provider.Settings
import android.util.Base64
import android.util.Log
import org.bouncycastle.crypto.params.Ed25519PublicKeyParameters
import org.bouncycastle.crypto.signers.Ed25519Signer
import org.json.JSONObject
import java.io.File
import java.security.MessageDigest
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.TimeZone
import javax.crypto.Cipher
import javax.crypto.Mac
import javax.crypto.spec.GCMParameterSpec
import javax.crypto.spec.SecretKeySpec

/**
 * Лицензирование v4 (Ed25519) — порт product_core (Python).
 *
 * Лицензия: строка "OL1-" + base64url( payload(7) + content_key(32) + sig(64) ).
 *   payload: product_id(1) variant_id(1) client_id(2) duration_months(2) flags(1)
 *   sig = Ed25519(приватный_ключ, payload + content_key + device_id)
 *
 * В приложение встроен ТОЛЬКО публичный ключ проверки → подделать лицензию нельзя.
 * Ключ контента приходит ВНУТРИ лицензии (его нет в APK) и хранится в device-bound
 * license.dat; им расшифровывается контент (assets зашифрованы маркером OLENC1).
 *
 * Ed25519 проверяется через BouncyCastle низкоуровнево (без JCA-провайдера —
 * чтобы не конфликтовать со встроенным в Android урезанным BouncyCastle).
 */
object Licensing {

    private const val TAG = "Licensing"
    private const val LICENSE_FILENAME = "license.dat"
    private const val ENC_SALT = "product-core-license-v3"   // соль шифрования license.dat (как в _protocol)
    private const val PBKDF2_ITERATIONS = 100_000
    private const val MAX_CLOCK_DRIFT_HOURS = 24
    private const val LICENSE_VERSION = 4
    private const val LICENSE_PREFIX = "OL1-"
    private val CONTENT_MAGIC = "OLENC1\n".toByteArray(Charsets.US_ASCII)   // старый (keystream)
    private val CONTENT_MAGIC2 = "OLENC2\n".toByteArray(Charsets.US_ASCII)  // AES-256-GCM (быстро)

    private var PUBLIC_KEY = ByteArray(0)   // Ed25519 публичный ключ (из product_config.json)
    private var PRODUCT_ID = 0
    private var contentKey: ByteArray? = null          // ключ контента активной лицензии
    private var embeddedContentKey: ByteArray? = null  // ключ контента, встроенный в сборку (для короткого ключа)

    fun init(publicKey: IntArray, productId: Int, embeddedKey: ByteArray? = null) {
        PUBLIC_KEY = ByteArray(publicKey.size) { (publicKey[it] and 0xFF).toByte() }
        PRODUCT_ID = productId
        embeddedContentKey = embeddedKey
    }

    /** Ключ расшифровки контента из активной лицензии (null, если не активировано). */
    fun getContentKey(): ByteArray? = contentKey

    // ─── Device ID ──────────────────────────────────────────────────

    @SuppressLint("HardwareIds")
    fun getDeviceId(context: Context): String {
        val raw = try {
            Settings.Secure.getString(context.contentResolver, Settings.Secure.ANDROID_ID) ?: ""
        } catch (e: Exception) { "" }
        val source = raw.ifBlank {
            "fallback-${android.os.Build.MANUFACTURER}-${android.os.Build.MODEL}-${android.os.Build.SERIAL}"
        }
        val sha = MessageDigest.getInstance("SHA-256").digest(source.toByteArray(Charsets.UTF_8))
        return sha.joinToString("") { "%02X".format(it) }.substring(0, 16)
    }

    // ─── Ed25519 (BouncyCastle, низкоуровнево) ──────────────────────

    private fun verifyEd25519(pub: ByteArray, msg: ByteArray, sig: ByteArray): Boolean = try {
        val signer = Ed25519Signer()
        signer.init(false, Ed25519PublicKeyParameters(pub, 0))
        signer.update(msg, 0, msg.size)
        signer.verifySignature(sig)
    } catch (e: Exception) { false }

    // ─── HMAC / keystream (совместимо с _protocol) ──────────────────

    private fun hmacSha256(key: ByteArray, data: ByteArray): ByteArray {
        val mac = Mac.getInstance("HmacSHA256")
        mac.init(SecretKeySpec(key, "HmacSHA256"))
        return mac.doFinal(data)
    }

    private fun keystreamXor(data: ByteArray, key: ByteArray): ByteArray {
        val out = ByteArray(data.size)
        var offset = 0; var counter = 0
        while (offset < data.size) {
            val cb = byteArrayOf(
                ((counter ushr 24) and 0xFF).toByte(), ((counter ushr 16) and 0xFF).toByte(),
                ((counter ushr 8) and 0xFF).toByte(), (counter and 0xFF).toByte())
            val bk = hmacSha256(key, cb)
            val end = minOf(offset + 32, data.size)
            for (j in offset until end) out[j] = (data[j].toInt() xor bk[j - offset].toInt()).toByte()
            offset += 32; counter++
        }
        return out
    }

    /** tag(16) + keystream — по прямому 32-байтному ключу. */
    private fun encryptRaw(plaintext: ByteArray, key: ByteArray): ByteArray {
        val ct = keystreamXor(plaintext, key)
        val tag = hmacSha256(key, ct).copyOfRange(0, 16)
        return tag + ct
    }

    private fun decryptRaw(raw: ByteArray, key: ByteArray): ByteArray? {
        if (raw.size < 17) return null
        val tag = raw.copyOfRange(0, 16)
        val ct = raw.copyOfRange(16, raw.size)
        val expected = hmacSha256(key, ct).copyOfRange(0, 16)
        var diff = 0
        for (i in tag.indices) diff = diff or (tag[i].toInt() xor expected[i].toInt())
        if (diff != 0) return null
        return keystreamXor(ct, key)
    }

    /** Расшифровка файла контента. OLENC2 — AES-GCM (быстро); OLENC1 — старый keystream; без маркера — plaintext (dev). */
    fun decryptContent(raw: ByteArray): ByteArray? {
        // OLENC2 — AES-256-GCM (аппаратное ускорение)
        if (raw.size >= CONTENT_MAGIC2.size && raw.copyOfRange(0, CONTENT_MAGIC2.size).contentEquals(CONTENT_MAGIC2)) {
            val key = contentKey ?: return null
            return try {
                val body = raw.copyOfRange(CONTENT_MAGIC2.size, raw.size)
                val nonce = body.copyOfRange(0, 12)
                val ct = body.copyOfRange(12, body.size)
                val c = Cipher.getInstance("AES/GCM/NoPadding")
                c.init(Cipher.DECRYPT_MODE, SecretKeySpec(key, "AES"), GCMParameterSpec(128, nonce))
                c.doFinal(ct)
            } catch (e: Exception) { null }
        }
        // OLENC1 — старый keystream (совместимость)
        if (raw.size >= CONTENT_MAGIC.size && raw.copyOfRange(0, CONTENT_MAGIC.size).contentEquals(CONTENT_MAGIC)) {
            val key = contentKey ?: return null
            return decryptRaw(raw.copyOfRange(CONTENT_MAGIC.size, raw.size), key)
        }
        return raw  // без маркера — dev plaintext
    }

    // ─── license.dat (шифруется ключом от device_id) ────────────────

    private fun pbkdf2(password: ByteArray, salt: ByteArray, iterations: Int, dkLen: Int): ByteArray {
        val hLen = 32; val blocks = (dkLen + hLen - 1) / hLen
        val out = ByteArray(dkLen); var off = 0
        for (i in 1..blocks) {
            val si = ByteArray(salt.size + 4)
            System.arraycopy(salt, 0, si, 0, salt.size)
            si[salt.size] = ((i ushr 24) and 0xFF).toByte(); si[salt.size + 1] = ((i ushr 16) and 0xFF).toByte()
            si[salt.size + 2] = ((i ushr 8) and 0xFF).toByte(); si[salt.size + 3] = (i and 0xFF).toByte()
            var u = hmacSha256(password, si); val t = u.copyOf()
            for (c in 2..iterations) { u = hmacSha256(password, u); for (k in t.indices) t[k] = (t[k].toInt() xor u[k].toInt()).toByte() }
            val n = minOf(hLen, dkLen - off); System.arraycopy(t, 0, out, off, n); off += n
        }
        return out
    }

    private fun deriveEncKey(deviceId: String) =
        pbkdf2(deviceId.toByteArray(Charsets.UTF_8), ENC_SALT.toByteArray(Charsets.UTF_8), PBKDF2_ITERATIONS, 32)

    private fun encryptLicense(data: JSONObject, deviceId: String) =
        encryptRaw(data.toString().toByteArray(Charsets.UTF_8), deriveEncKey(deviceId))

    private fun decryptLicense(raw: ByteArray, deviceId: String): JSONObject? {
        val pt = decryptRaw(raw, deriveEncKey(deviceId)) ?: return null
        return try { JSONObject(String(pt, Charsets.UTF_8)) } catch (e: Exception) { null }
    }

    // ─── Утилиты ────────────────────────────────────────────────────

    private fun isoFormat(d: Date): String =
        SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss", Locale.US).apply { timeZone = TimeZone.getDefault() }.format(d)
    private fun parseIso(s: String): Date? = try {
        SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss", Locale.US).apply { timeZone = TimeZone.getDefault() }.parse(s)
    } catch (e: Exception) { null }
    private fun sha256Hex(s: String) =
        MessageDigest.getInstance("SHA-256").digest(s.toByteArray(Charsets.UTF_8)).joinToString("") { "%02x".format(it) }
    private fun monthsWord(n: Int): String {
        if (n % 100 in 11..19) return "месяцев"
        return when (n % 10) { 1 -> "месяц"; 2, 3, 4 -> "месяца"; else -> "месяцев" }
    }
    private fun licenseFile(c: Context) = File(c.filesDir, LICENSE_FILENAME)

    data class LicenseStatus(
        val valid: Boolean, val reason: String,
        val variantId: Int? = null, val expiresAt: String? = null, val daysLeft: Int? = null
    )

    private data class Decoded(val payload: ByteArray, val contentKey: ByteArray,
                              val productId: Int, val variantId: Int, val clientId: Int, val duration: Int)

    // ─── Валидация лицензии ─────────────────────────────────────────

    private fun validate(licenseStr: String, context: Context): Pair<Decoded?, String> {
        var s = licenseStr.trim().replace(" ", "").replace("\n", "")
        if (s.startsWith(LICENSE_PREFIX)) s = s.substring(LICENSE_PREFIX.length)
        val raw = try {
            Base64.decode(s, Base64.URL_SAFE or Base64.NO_PADDING or Base64.NO_WRAP)
        } catch (e: Exception) { return null to "Неверный формат лицензии" }
        if (raw.size != 7 + 32 + 64) return null to "Неверный формат лицензии"

        val payload = raw.copyOfRange(0, 7)
        val ck = raw.copyOfRange(7, 39)
        val sig = raw.copyOfRange(39, 103)
        val deviceId = getDeviceId(context)
        val msg = payload + ck + deviceId.uppercase().toByteArray(Charsets.UTF_8)
        if (!verifyEd25519(PUBLIC_KEY, msg, sig)) return null to "Лицензия не подходит для этого устройства"

        val productId = payload[0].toInt() and 0xFF
        val variantId = payload[1].toInt() and 0xFF
        val clientId = ((payload[2].toInt() and 0xFF) shl 8) or (payload[3].toInt() and 0xFF)
        val duration = ((payload[4].toInt() and 0xFF) shl 8) or (payload[5].toInt() and 0xFF)
        if (productId != PRODUCT_ID) return null to "Лицензия от другого продукта"
        return Decoded(payload, ck, productId, variantId, clientId, duration) to ""
    }

    fun activateLicense(context: Context, licenseStr: String): Pair<Boolean, String> {
        val s = licenseStr.trim()
        return if (s.startsWith(LICENSE_PREFIX)) activateLong(context, s) else activateShort(context, s)
    }

    // ─── Короткий ключ (20 симв., симметричный, MAC на встроенном ключе контента) ───

    private data class ShortInfo(val variant: Int, val client: Int, val months: Int)

    private fun base32Decode(s: String): ByteArray? {
        val alpha = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"
        var buffer = 0L; var bits = 0
        val out = java.io.ByteArrayOutputStream()
        for (ch in s) {
            val v = alpha.indexOf(ch); if (v < 0) return null
            buffer = (buffer shl 5) or v.toLong(); bits += 5
            if (bits >= 8) { bits -= 8; out.write(((buffer shr bits) and 0xFFL).toInt()) }
        }
        return out.toByteArray()
    }

    private fun decodeShort(keyStr: String, key: ByteArray, deviceId: String): ShortInfo? {
        val s = keyStr.uppercase().replace("-", "").replace(" ", "").trim()
        val raw = base32Decode(s) ?: return null
        if (raw.size != 12) return null
        val payload = raw.copyOfRange(0, 4)
        val mac = raw.copyOfRange(4, 12)
        val expect = hmacSha256(key, payload + deviceId.uppercase().toByteArray(Charsets.UTF_8)).copyOfRange(0, 8)
        var diff = 0
        for (i in mac.indices) diff = diff or (mac[i].toInt() xor expect[i].toInt())
        if (diff != 0) return null
        val variant = payload[0].toInt() and 0xFF
        val client = ((payload[1].toInt() and 0xFF) shl 8) or (payload[2].toInt() and 0xFF)
        val months = payload[3].toInt() and 0xFF
        return ShortInfo(variant, client, months)
    }

    private fun activateShort(context: Context, keyStr: String): Pair<Boolean, String> {
        val key = embeddedContentKey ?: return false to "Активация по короткому ключу недоступна в этой сборке"
        val deviceId = getDeviceId(context)
        val info = decodeShort(keyStr, key, deviceId) ?: return false to "Ключ неверен или не для этого устройства"
        val now = Date()
        val expires = Date(now.time + info.months.toLong() * 30L * 24L * 3600L * 1000L)
        val data = JSONObject().apply {
            put("key_hash", sha256Hex(keyStr.trim().uppercase()))
            put("device_id", deviceId); put("product_id", PRODUCT_ID)
            put("variant_id", info.variant); put("client_id", info.client)
            put("duration_months", info.months)
            put("activated_at", isoFormat(now)); put("expires_at", isoFormat(expires))
            put("last_check", isoFormat(now)); put("version", LICENSE_VERSION); put("short", true)
        }
        return try {
            licenseFile(context).writeBytes(encryptLicense(data, deviceId))
            contentKey = key
            true to "Активация успешна! Лицензия действительна ${info.months} ${monthsWord(info.months)}."
        } catch (e: Exception) {
            Log.e(TAG, "Ошибка сохранения", e); false to "Ошибка сохранения лицензии: ${e.message}"
        }
    }

    private fun activateLong(context: Context, licenseStr: String): Pair<Boolean, String> {
        val (d, err) = validate(licenseStr, context)
        if (d == null) return false to err
        val deviceId = getDeviceId(context)
        val now = Date()
        val expires = Date(now.time + d.duration.toLong() * 30L * 24L * 3600L * 1000L)
        val data = JSONObject().apply {
            put("key_hash", sha256Hex(licenseStr.trim()))
            put("device_id", deviceId)
            put("product_id", d.productId); put("variant_id", d.variantId); put("client_id", d.clientId)
            put("duration_months", d.duration)
            put("content_key", d.contentKey.joinToString("") { "%02x".format(it) })
            put("activated_at", isoFormat(now)); put("expires_at", isoFormat(expires))
            put("last_check", isoFormat(now)); put("version", LICENSE_VERSION)
        }
        return try {
            licenseFile(context).writeBytes(encryptLicense(data, deviceId))
            contentKey = d.contentKey
            true to "Активация успешна! Лицензия действительна ${d.duration} ${monthsWord(d.duration)}."
        } catch (e: Exception) {
            Log.e(TAG, "Ошибка сохранения", e); false to "Ошибка сохранения лицензии: ${e.message}"
        }
    }

    fun getLicenseStatus(context: Context): LicenseStatus {
        val file = licenseFile(context)
        if (!file.exists()) return LicenseStatus(false, "Лицензия не найдена")
        val raw = try { file.readBytes() } catch (e: Exception) { return LicenseStatus(false, "Ошибка чтения файла") }
        val deviceId = getDeviceId(context)
        val data = decryptLicense(raw, deviceId)
            ?: return LicenseStatus(false, "Лицензия повреждена или принадлежит другому устройству")
        if (data.optInt("version") != LICENSE_VERSION) return LicenseStatus(false, "Устаревший формат лицензии")
        if (data.optString("device_id") != deviceId) return LicenseStatus(false, "Лицензия привязана к другому устройству")
        if (data.optInt("product_id") != PRODUCT_ID) return LicenseStatus(false, "Лицензия от другого продукта")

        val now = Date()
        val lastCheck = parseIso(data.optString("last_check", ""))
        if (lastCheck != null && (lastCheck.time - now.time) > MAX_CLOCK_DRIFT_HOURS * 3600L * 1000L)
            return LicenseStatus(false, "Обнаружено изменение системных часов.")
        val expiresAt = parseIso(data.optString("expires_at", "")) ?: return LicenseStatus(false, "Повреждены данные лицензии")
        if (now.after(expiresAt)) return LicenseStatus(false, "Срок действия лицензии истёк", expiresAt = data.optString("expires_at"))

        // загрузить ключ контента в память
        val ckHex = data.optString("content_key", "")
        if (ckHex.length == 64) contentKey = ByteArray(32) { ((Character.digit(ckHex[it*2],16) shl 4) or Character.digit(ckHex[it*2+1],16)).toByte() }
        else if (data.optBoolean("short", false)) contentKey = embeddedContentKey   // короткий ключ — ключ контента встроен

        val daysLeft = ((expiresAt.time - now.time) / (24L * 3600L * 1000L)).toInt()
        try { data.put("last_check", isoFormat(now)); file.writeBytes(encryptLicense(data, deviceId)) } catch (e: Exception) {}
        return LicenseStatus(true, "OK", data.optInt("variant_id"), data.optString("expires_at"), daysLeft)
    }

    fun isActivated(context: Context): Boolean = getLicenseStatus(context).valid
}
