package kz.digitouch.shell

import android.annotation.SuppressLint
import android.os.Bundle
import android.util.Log
import android.view.View
import android.view.WindowManager
import android.webkit.JavascriptInterface
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebView
import android.webkit.WebViewClient
import android.app.AlertDialog
import android.widget.Button
import androidx.appcompat.app.AppCompatActivity
import android.Manifest
import android.content.pm.PackageManager
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.content.ContextCompat
import android.content.Intent
import androidx.webkit.WebViewAssetLoader
import org.json.JSONObject
import java.io.ByteArrayInputStream
import java.io.FileNotFoundException
import java.io.IOException

/**
 * WebView-оболочка (v4). Конфигурация — assets/product_config.json:
 *   product_id, public_key (Ed25519), entry_html, window_title, anti_copy, flag_secure, skip_activation
 *
 * Контент в assets зашифрован (OLENC1) и отдаётся через WebViewAssetLoader с
 * расшифровкой В ПАМЯТИ по ключу из активной лицензии (как loopback на десктопе).
 * Без лицензии ключа нет → контент не отдаётся.
 */
class MainActivity : AppCompatActivity() {

    companion object {
        private const val TAG = "ProductShell"
        private const val DOMAIN = "appassets.androidplatform.net"
    }

    private lateinit var webView: WebView
    private lateinit var btnDeviceId: Button
    private var config = JSONObject()
    private lateinit var assetLoader: WebViewAssetLoader

    // QR-сканер лицензии (ZXing) + разрешение камеры
    private val scanLauncher = registerForActivityResult(ActivityResultContracts.StartActivityForResult()) { res ->
        if (res.resultCode == RESULT_OK) {
            val text = res.data?.getStringExtra("qr")
            if (text != null) activateWith(text)
        }
    }

    private val cameraPermLauncher = registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        if (granted) launchScan()
        else runOnUiThread { webView.evaluateJavascript("if(typeof onActivationError==='function')onActivationError('Нет доступа к камере');", null) }
    }
    private fun launchScan() {
        scanLauncher.launch(Intent(this, QrScanActivity::class.java))
    }
    private fun activateWith(key: String) {
        val (ok, message) = Licensing.activateLicense(this, key)
        val esc = message.replace("\\", "\\\\").replace("'", "\\'")
        runOnUiThread {
            if (ok) {
                webView.evaluateJavascript("if(typeof onActivationSuccess==='function')onActivationSuccess('$esc');", null)
                webView.postDelayed({ loadContent() }, 1200L)
            } else {
                webView.evaluateJavascript("if(typeof onActivationError==='function')onActivationError('$esc');", null)
            }
        }
    }

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        config = loadConfig()

        window.setFlags(WindowManager.LayoutParams.FLAG_FULLSCREEN, WindowManager.LayoutParams.FLAG_FULLSCREEN)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        if (config.optBoolean("flag_secure", true))
            window.addFlags(WindowManager.LayoutParams.FLAG_SECURE)

        setContentView(R.layout.activity_main)
        webView = findViewById(R.id.webView)
        btnDeviceId = findViewById(R.id.btnDeviceId)

        // Лицензирование: публичный ключ (длинная лицензия) + встроенный ключ контента (короткий ключ)
        val pub = config.optJSONArray("public_key")
        val productId = config.optInt("product_id", 0)
        var embeddedKey: ByteArray? = null
        val ckMask = config.optJSONArray("ck_mask")
        val ckData = config.optJSONArray("ck_data")
        if (ckMask != null && ckData != null && ckMask.length() == 32 && ckData.length() == 32) {
            embeddedKey = ByteArray(32) { ((ckMask.getInt(it) xor ckData.getInt(it)) and 0xFF).toByte() }
        }
        Licensing.init(if (pub != null) IntArray(pub.length()) { pub.getInt(it) } else IntArray(0), productId, embeddedKey)

        btnDeviceId.setOnClickListener {
            AlertDialog.Builder(this)
                .setTitle("Device ID")
                .setMessage("ID этого устройства:\n\n${Licensing.getDeviceId(this)}\n\nСообщите его для получения лицензии.")
                .setPositiveButton("OK", null).show()
        }

        // Отдача контента: зашифрованные assets/content/* (расшифровка в памяти) + assets/templates/* (plaintext)
        assetLoader = WebViewAssetLoader.Builder()
            .setDomain(DOMAIN)
            .addPathHandler("/content/", AssetPathHandler("content", decrypt = true))
            .addPathHandler("/templates/", AssetPathHandler("templates", decrypt = false))
            .build()

        webView.setLayerType(View.LAYER_TYPE_HARDWARE, null)
        webView.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
            allowFileAccess = false
            allowContentAccess = false
            setSupportZoom(true); builtInZoomControls = true; displayZoomControls = false
            loadWithOverviewMode = true; useWideViewPort = true
            mediaPlaybackRequiresUserGesture = false
        }
        webView.webChromeClient = WebChromeClient()
        webView.webViewClient = object : WebViewClient() {
            override fun shouldInterceptRequest(view: WebView?, request: WebResourceRequest?): WebResourceResponse? =
                request?.url?.let { assetLoader.shouldInterceptRequest(it) }
            override fun onPageFinished(view: WebView?, url: String?) {
                super.onPageFinished(view, url)
                if (config.optBoolean("anti_copy", true)) injectAntiCopy()
            }
        }
        webView.setOnLongClickListener { true }
        webView.isLongClickable = false

        // JS-мост (sync). activation.html строит из него window.core.
        webView.addJavascriptInterface(JsBridge(), "AndroidShell")

        if (config.optBoolean("skip_activation", false) || Licensing.isActivated(this)) loadContent()
        else showActivation()
    }

    private fun loadConfig(): JSONObject = try {
        JSONObject(assets.open("product_config.json").bufferedReader().use { it.readText() })
    } catch (e: IOException) { Log.e(TAG, "нет product_config.json", e); JSONObject() }

    private fun showActivation() {
        btnDeviceId.visibility = View.VISIBLE
        webView.loadUrl("https://$DOMAIN/templates/activation.html")
    }

    private fun loadContent() {
        btnDeviceId.visibility = View.GONE
        webView.loadUrl("https://$DOMAIN/content/${config.optString("entry_html", "index.html")}")
    }

    private fun injectAntiCopy() {
        webView.evaluateJavascript("""
            (function(){var s=document.createElement('style');
              s.textContent='*{-webkit-user-select:none!important;user-select:none!important;-webkit-touch-callout:none!important;}'+
                'input,textarea{-webkit-user-select:text!important;user-select:text!important;}';
              document.head.appendChild(s);
              ['copy','cut','dragstart'].forEach(function(ev){document.addEventListener(ev,function(e){e.preventDefault();},true);});
              document.addEventListener('contextmenu',function(e){e.preventDefault();},true);})();
        """.trimIndent(), null)
    }

    @Deprecated("Deprecated in Java")
    override fun onBackPressed() { if (webView.canGoBack()) webView.goBack() else super.onBackPressed() }

    // ─── Отдача assets с опциональной расшифровкой ──────────────────

    private inner class AssetPathHandler(private val root: String, private val decrypt: Boolean) :
        WebViewAssetLoader.PathHandler {
        override fun handle(path: String): WebResourceResponse? {
            return try {
                val raw = assets.open("$root/$path").use { it.readBytes() }
                val data = if (decrypt) (Licensing.decryptContent(raw)
                    ?: return WebResourceResponse("text/plain", "UTF-8", 403, "Locked",
                        emptyMap(), ByteArrayInputStream(ByteArray(0)))) else raw
                val mime = mimeFor(path)
                WebResourceResponse(mime, if (isText(mime)) "UTF-8" else null, ByteArrayInputStream(data))
            } catch (e: FileNotFoundException) { null } catch (e: Exception) {
                Log.e(TAG, "ошибка отдачи $root/$path", e); null
            }
        }
    }

    private fun mimeFor(path: String): String = when (path.substringAfterLast('.', "").lowercase()) {
        "html", "htm" -> "text/html"; "js", "mjs" -> "application/javascript"; "css" -> "text/css"
        "json", "map" -> "application/json"; "svg" -> "image/svg+xml"; "png" -> "image/png"
        "jpg", "jpeg" -> "image/jpeg"; "gif" -> "image/gif"; "webp" -> "image/webp"; "ico" -> "image/x-icon"
        "woff" -> "font/woff"; "woff2" -> "font/woff2"; "ttf" -> "font/ttf"; "otf" -> "font/otf"
        "glb" -> "model/gltf-binary"; "gltf" -> "model/gltf+json"; "wasm" -> "application/wasm"
        "mp3" -> "audio/mpeg"; "wav" -> "audio/wav"; "ogg" -> "audio/ogg"; "mp4" -> "video/mp4"
        else -> "application/octet-stream"
    }
    private fun isText(m: String) = m.startsWith("text/") || m == "application/javascript" || m == "application/json" || m == "image/svg+xml"

    // ─── JS-мост ────────────────────────────────────────────────────

    inner class JsBridge {
        @JavascriptInterface fun getDeviceId(): String = Licensing.getDeviceId(this@MainActivity)
        @JavascriptInterface fun getStatus(): String {
            val s = Licensing.getLicenseStatus(this@MainActivity)
            return JSONObject().apply {
                put("valid", s.valid); put("reason", s.reason)
                put("variant_id", s.variantId ?: JSONObject.NULL)
                put("expires_at", s.expiresAt ?: JSONObject.NULL)
                put("days_left", s.daysLeft ?: JSONObject.NULL)
            }.toString()
        }
        @JavascriptInterface fun activateKey(key: String) { activateWith(key) }
        @JavascriptInterface fun scanQr() {
            runOnUiThread {
                if (ContextCompat.checkSelfPermission(this@MainActivity, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED) launchScan()
                else cameraPermLauncher.launch(Manifest.permission.CAMERA)
            }
        }

        @JavascriptInterface fun log(msg: String) { Log.i(TAG, "[web] $msg") }
    }
}
