package kz.digitouch.shell

import android.content.Context
import android.provider.Settings
import android.util.Log
import org.json.JSONObject
import java.io.File
import java.security.MessageDigest
import java.text.SimpleDateFormat
import java.util.Calendar
import java.util.Date
import java.util.Locale
import java.util.TimeZone
import javax.crypto.Mac
import javax.crypto.SecretKeyFactory
import javax.crypto.spec.PBEKeySpec
import javax.crypto.spec.SecretKeySpec

/**
 * Лицензирование LEGACY-20 — короткий ключ XXXX-XXXX-XXXX-XXXX-XXXX.
 *
 * Это СТАРАЯ схема (v2), сохранённая как запасной вариант: активация вводится
 * руками, QR-сканера нет вовсе. Отличия от боевого ядра v4:
 *   - ключ 20 символов (Base32) вместо строки OL1-… на 142 символа;
 *   - подпись симметричная (HMAC-SHA256) вместо Ed25519;
 *   - секрет подписи лежит В APK (в product_config.json);
 *   - контент НЕ шифруется.
 * Из-за последних двух пунктов контент из APK извлекаем — использовать только
 * там, где короткий ввод важнее защиты контента.
 *
 * Формат ключа:
 *   payload(4 байта, big-endian uint32):
 *     биты 31-28 : variant_id       (0-15; 0 = «все предметы»)
 *     биты 27-12 : client_id        (0-65535)
 *     биты 11-4  : duration_months  (1-255)
 *     биты 3-0   : flags            (резерв)
 *   ключ = payload(4) + HMAC-SHA256(secret, payload + device_id)[:8] = 12 байт
 *   Base32 → 20 символов → XXXX-XXXX-XXXX-XXXX-XXXX
 *
 * device_id входит в подпись, поэтому ключ работает только на своей доске.
 */
object Licensing {

    private const val TAG = "Licensing"
    private const val LICENSE_FILENAME = "license.dat"
    private const val ENC_SALT = "oi-orda-legacy20-license"
    private const val PBKDF2_ITERATIONS = 100_000
    private const val MAX_CLOCK_DRIFT_HOURS = 24
    private const val LICENSE_VERSION = 2

    // Секрет HMAC и вариант сборки берём из assets/product_config.json
    private var SECRET = ByteArray(0)
    private var VARIANT_ID = 0
    private var PRODUCT_ID = 0
    private var loaded = false

    /**
     * Совместимость с оболочкой. В LEGACY-20 публичный ключ и ключ контента не
     * нужны: подпись симметричная, контент не шифруется. Принимаем те же
     * аргументы, что и боевое ядро, чтобы MainActivity не пришлось менять.
     */
    fun init(publicKey: IntArray, productId: Int, embeddedKey: ByteArray? = null) {
        PRODUCT_ID = productId
    }

    /**
     * Контент в этой сборке лежит открытым — отдаём как есть.
     * Оставлено ради единого кода отдачи ассетов в MainActivity.
     */
    fun decryptContent(raw: ByteArray): ByteArray? = raw

    /** Читает product_config.json (секрет подписи + вариант). */
    private fun ensureLoaded(context: Context) {
        if (loaded) return
        try {
            val cfg = JSONObject(
                context.assets.open("product_config.json").bufferedReader().use { it.readText() })
            VARIANT_ID = cfg.optInt("variant_id", 0)
            val arr = cfg.optJSONArray("hmac_secret")
            if (arr != null) {
                SECRET = ByteArray(arr.length()) { (arr.getInt(it) and 0xFF).toByte() }
            } else {
                Log.e(TAG, "hmac_secret отсутствует — активация работать не будет")
            }
        } catch (e: Exception) {
            Log.e(TAG, "product_config.json не прочитан: ${e.message}")
        }
        loaded = true
    }

    // ─── Device ID ──────────────────────────────────────────────────
    fun getDeviceId(context: Context): String {
        val androidId = try {
            Settings.Secure.getString(context.contentResolver, Settings.Secure.ANDROID_ID) ?: ""
        } catch (e: Exception) {
            ""
        }
        val src = if (androidId.isNotBlank() && androidId != "9774d56d682e549c") androidId
                  else android.os.Build.FINGERPRINT + android.os.Build.MODEL
        return sha256Hex(src).substring(0, 16).uppercase(Locale.US)
    }

    // ─── Base32 (RFC 4648, без padding) ─────────────────────────────
    private const val BASE32_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"

    private fun base32Decode(input: String): ByteArray? {
        val clean = input.replace("-", "").replace(" ", "").uppercase(Locale.US)
        if (clean.isEmpty()) return null
        var buffer = 0
        var bitsLeft = 0
        val out = ArrayList<Byte>()
        for (ch in clean) {
            val idx = BASE32_ALPHABET.indexOf(ch)
            if (idx < 0) return null
            buffer = (buffer shl 5) or idx
            bitsLeft += 5
            if (bitsLeft >= 8) {
                out.add(((buffer shr (bitsLeft - 8)) and 0xFF).toByte())
                bitsLeft -= 8
            }
        }
        return out.toByteArray()
    }

    // ─── HMAC-SHA256 ────────────────────────────────────────────────
    private fun hmacSha256(key: ByteArray, data: ByteArray): ByteArray {
        val mac = Mac.getInstance("HmacSHA256")
        mac.init(SecretKeySpec(key, "HmacSHA256"))
        return mac.doFinal(data)
    }

    data class KeyPayload(
        val variantId: Int,
        val clientId: Int,
        val durationMonths: Int,
        val flags: Int,
    )

    /** Проверяет ключ и его привязку к этой доске. */
    fun validateKey(keyStr: String, context: Context): Pair<KeyPayload?, String> {
        ensureLoaded(context)
        if (SECRET.isEmpty()) return null to "Сборка без ключа подписи"

        val clean = keyStr.replace("-", "").replace(" ", "").uppercase(Locale.US)
        if (clean.length != 20) return null to "Ключ должен быть из 20 символов"

        val raw = base32Decode(clean) ?: return null to "В ключе недопустимые символы"
        if (raw.size != 12) return null to "Неверный размер ключа"

        val payload = raw.copyOfRange(0, 4)
        val sig = raw.copyOfRange(4, 12)

        val deviceId = getDeviceId(context)
        val expected = hmacSha256(SECRET, payload + deviceId.toByteArray()).copyOfRange(0, 8)
        if (!MessageDigest.isEqual(sig, expected)) {
            return null to "Ключ не подходит для этого устройства"
        }

        var v = 0L
        for (b in payload) v = (v shl 8) or (b.toLong() and 0xFF)
        val variantId = ((v shr 28) and 0xF).toInt()
        val clientId = ((v shr 12) and 0xFFFF).toInt()
        val months = ((v shr 4) and 0xFF).toInt()
        val flags = (v and 0xF).toInt()

        if (months < 1) return null to "Некорректный срок действия"
        // Сборка предмета принимает только свой ключ; 0 = «все предметы» подходит всем.
        if (VARIANT_ID != 0 && variantId != 0 && variantId != VARIANT_ID) {
            return null to "Ключ выдан на другой предмет"
        }
        return KeyPayload(variantId, clientId, months, flags) to ""
    }

    // ─── Хранение лицензии (привязано к устройству) ─────────────────
    private fun pbkdf2(password: String, salt: ByteArray, iterations: Int, bytes: Int): ByteArray {
        val spec = PBEKeySpec(password.toCharArray(), salt, iterations, bytes * 8)
        return SecretKeyFactory.getInstance("PBKDF2WithHmacSHA256").generateSecret(spec).encoded
    }

    private fun deriveEncKey(deviceId: String): ByteArray =
        pbkdf2(deviceId + ENC_SALT, ENC_SALT.toByteArray(), PBKDF2_ITERATIONS, 32)

    private fun xorCrypt(data: ByteArray, key: ByteArray): ByteArray {
        // Потоковое гаммирование на HMAC — как в старой сборке плакатов.
        val out = ByteArray(data.size)
        var counter = 0
        var block = ByteArray(0)
        var bi = 0
        for (i in data.indices) {
            if (bi >= block.size) {
                block = hmacSha256(key, "stream$counter".toByteArray())
                counter++
                bi = 0
            }
            out[i] = (data[i].toInt() xor block[bi].toInt()).toByte()
            bi++
        }
        return out
    }

    private fun licenseFile(context: Context): File = File(context.filesDir, LICENSE_FILENAME)

    private fun saveLicense(context: Context, obj: JSONObject) {
        val deviceId = getDeviceId(context)
        val key = deriveEncKey(deviceId)
        val body = obj.toString().toByteArray()
        val mac = hmacSha256(key, body).copyOfRange(0, 16)
        licenseFile(context).writeBytes(xorCrypt(mac + body, key))
    }

    private fun loadLicense(context: Context): JSONObject? {
        val f = licenseFile(context)
        if (!f.exists()) return null
        return try {
            val key = deriveEncKey(getDeviceId(context))
            val plain = xorCrypt(f.readBytes(), key)
            if (plain.size <= 16) return null
            val mac = plain.copyOfRange(0, 16)
            val body = plain.copyOfRange(16, plain.size)
            if (!MessageDigest.isEqual(mac, hmacSha256(key, body).copyOfRange(0, 16))) {
                Log.w(TAG, "license.dat повреждён или скопирован с другой доски")
                return null
            }
            JSONObject(String(body))
        } catch (e: Exception) {
            Log.w(TAG, "license.dat не прочитан: ${e.message}")
            null
        }
    }

    // ─── Активация ──────────────────────────────────────────────────
    /** Возвращает (успех, сообщение для экрана активации). */
    fun activateLicense(context: Context, keyStr: String): Pair<Boolean, String> {
        val (payload, err) = validateKey(keyStr, context)
        if (payload == null) return false to err

        val now = Date()
        val cal = Calendar.getInstance()
        cal.time = now
        cal.add(Calendar.MONTH, payload.durationMonths)
        val expires = cal.time

        val obj = JSONObject().apply {
            put("version", LICENSE_VERSION)
            put("key", keyStr.uppercase(Locale.US))
            put("variant_id", payload.variantId)
            put("client_id", payload.clientId)
            put("months", payload.durationMonths)
            put("activated_at", isoFormat(now))
            put("expires_at", isoFormat(expires))
            put("device_id", getDeviceId(context))
        }
        return try {
            saveLicense(context, obj)
            true to "Активировано на ${payload.durationMonths} ${monthsWord(payload.durationMonths)}"
        } catch (e: Exception) {
            false to "Не удалось сохранить лицензию: ${e.message}"
        }
    }

    // Совпадает по типам с боевым ядром — оболочка одна и та же.
    data class LicenseStatus(
        val valid: Boolean, val reason: String,
        val variantId: Int? = null, val expiresAt: String? = null, val daysLeft: Int? = null
    )

    fun getLicenseStatus(context: Context): LicenseStatus {
        val obj = loadLicense(context) ?: return LicenseStatus(false, "Не активировано")

        if (obj.optString("device_id") != getDeviceId(context)) {
            return LicenseStatus(false, "Лицензия выдана другому устройству")
        }
        val expires = parseIso(obj.optString("expires_at"))
            ?: return LicenseStatus(false, "Повреждена дата окончания")
        val activated = parseIso(obj.optString("activated_at"))
        val variant = obj.optInt("variant_id", 0)

        val now = Date()
        // Защита от перевода часов назад
        if (activated != null &&
            now.time < activated.time - MAX_CLOCK_DRIFT_HOURS * 3600_000L) {
            return LicenseStatus(false, "Часы устройства переведены назад")
        }
        if (now.after(expires)) {
            return LicenseStatus(false, "Срок лицензии истёк", variant, isoFormat(expires), 0)
        }
        val days = ((expires.time - now.time) / 86_400_000L).toInt()
        return LicenseStatus(true, "", variant, isoFormat(expires), days)
    }

    fun isActivated(context: Context): Boolean = getLicenseStatus(context).valid

    fun deactivate(context: Context) {
        try {
            licenseFile(context).delete()
        } catch (e: Exception) {
            Log.w(TAG, "не удалось удалить license.dat: ${e.message}")
        }
    }

    // ─── Мелочи ─────────────────────────────────────────────────────
    private fun isoFormat(date: Date): String {
        val f = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss", Locale.US)
        f.timeZone = TimeZone.getTimeZone("UTC")
        return f.format(date)
    }

    private fun parseIso(s: String): Date? = try {
        if (s.isBlank()) null else {
            val f = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss", Locale.US)
            f.timeZone = TimeZone.getTimeZone("UTC")
            f.parse(s)
        }
    } catch (e: Exception) {
        null
    }

    private fun monthsWord(n: Int): String {
        val a = n % 100
        val b = n % 10
        return when {
            a in 11..14 -> "месяцев"
            b == 1 -> "месяц"
            b in 2..4 -> "месяца"
            else -> "месяцев"
        }
    }

    private fun sha256Hex(s: String): String =
        MessageDigest.getInstance("SHA-256").digest(s.toByteArray())
            .joinToString("") { "%02x".format(it) }
}
