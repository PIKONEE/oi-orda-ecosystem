package kz.digitouch.shell

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.net.Uri
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.util.Size
import android.widget.Button
import android.widget.TextView
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.camera.core.CameraSelector
import androidx.camera.core.CameraState
import androidx.camera.core.ExperimentalGetImage
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageProxy
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.core.content.ContextCompat
import com.google.mlkit.vision.barcode.BarcodeScannerOptions
import com.google.mlkit.vision.barcode.BarcodeScanning
import com.google.mlkit.vision.barcode.common.Barcode
import com.google.mlkit.vision.common.InputImage
import java.util.concurrent.Executors

/**
 * Сканер QR: CameraX + ML Kit (модель вшита, офлайн).
 *
 * Устойчивость к отказам камеры на досках:
 *  - перебор ВСЕХ камер (фронт → тыл → внешние USB, LENS_FACING_EXTERNAL);
 *  - если preview+analysis не биндится (старые HAL) — повтор только с analysis;
 *  - наблюдение CameraState: камера занята/отвалилась — понятное сообщение;
 *  - «QR из файла» — распознавание QR из сохранённой картинки, камера не нужна;
 *  - «Ввести ключ вручную» — возврат на экран активации к полю ввода;
 *  - подсказка, если за 25 секунд ничего не отсканировалось.
 * Режим EXTRA_NO_CAMERA: камера не инициализируется (нет разрешения) —
 * остаются файл и ручной ввод.
 */
class QrScanActivity : AppCompatActivity() {

    companion object {
        const val EXTRA_NO_CAMERA = "no_camera"
    }

    private lateinit var previewView: PreviewView
    private lateinit var txtStatus: TextView
    private val exec = Executors.newSingleThreadExecutor()
    private val mainHandler = Handler(Looper.getMainLooper())
    private var provider: ProcessCameraProvider? = null
    private var lensFacing = CameraSelector.LENS_FACING_FRONT
    private var cameraOk = false
    @Volatile private var handled = false

    private val scanner = BarcodeScanning.getClient(
        BarcodeScannerOptions.Builder().setBarcodeFormats(Barcode.FORMAT_QR_CODE).build())

    // ─── Выбор картинки с QR ────────────────────────────────────────
    // Штатный путь — SAF (OpenDocument): всегда отдаёт content:// с выданным
    // правом чтения. Встроенные файловые менеджеры досок нередко возвращают
    // file:// — тогда читаем файл напрямую, при необходимости спросив
    // разрешение на хранилище (иначе open failed EACCES).
    private val pickImageSaf = registerForActivityResult(
        ActivityResultContracts.OpenDocument()) { uri -> uri?.let { decodeQrFromUri(it) } }

    private val pickImageLegacy = registerForActivityResult(
        ActivityResultContracts.GetContent()) { uri -> uri?.let { decodeQrFromUri(it) } }

    private var pendingUri: Uri? = null
    private val storagePermLauncher = registerForActivityResult(
        ActivityResultContracts.RequestPermission()) { granted ->
        val u = pendingUri
        pendingUri = null
        if (granted && u != null) decodeQrFromUri(u, afterPermission = true)
        else Toast.makeText(this,
            "Нет доступа к файлу. Выберите картинку через «Файлы» или введите ключ вручную.",
            Toast.LENGTH_LONG).show()
    }

    private fun storagePermission(): String =
        if (android.os.Build.VERSION.SDK_INT >= 33) Manifest.permission.READ_MEDIA_IMAGES
        else Manifest.permission.READ_EXTERNAL_STORAGE

    private fun pickImage() {
        // SAF доступен не на всех прошивках досок — если активити нет, идём legacy-путём
        try {
            pickImageSaf.launch(arrayOf("image/*"))
        } catch (e: Exception) {
            try {
                pickImageLegacy.launch("image/*")
            } catch (e2: Exception) {
                Toast.makeText(this, "Не найдено приложение для выбора файла: ${e2.message}",
                    Toast.LENGTH_LONG).show()
            }
        }
    }

    /** Читает картинку и по content://, и по file://; крупные ужимает, чтобы не словить OOM. */
    private fun loadBitmap(uri: Uri): Bitmap? {
        fun open(): java.io.InputStream? = try {
            contentResolver.openInputStream(uri)
        } catch (e: Exception) {
            val p = uri.path
            if (uri.scheme == "file" && p != null) {
                val f = java.io.File(p)
                if (f.canRead()) java.io.FileInputStream(f) else null
            } else null
        }

        // 1) габариты — чтобы посчитать коэффициент уменьшения
        val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        open()?.use { BitmapFactory.decodeStream(it, null, bounds) } ?: return null

        var sample = 1
        val maxSide = maxOf(bounds.outWidth, bounds.outHeight)
        while (maxSide / sample > 2200) sample *= 2

        // 2) собственно декодирование
        val opts = BitmapFactory.Options().apply { inSampleSize = sample }
        return open()?.use { BitmapFactory.decodeStream(it, null, opts) }
    }

    private fun decodeQrFromUri(uri: Uri, afterPermission: Boolean = false) {
        val bmp = try {
            loadBitmap(uri)
        } catch (e: Exception) {
            null
        }

        if (bmp == null) {
            // Скорее всего file:// без разрешения на хранилище — спросим один раз
            val needsPerm = uri.scheme == "file" && !afterPermission &&
                ContextCompat.checkSelfPermission(this, storagePermission()) !=
                    PackageManager.PERMISSION_GRANTED
            if (needsPerm) {
                pendingUri = uri
                storagePermLauncher.launch(storagePermission())
            } else {
                Toast.makeText(this,
                    "Не удалось открыть файл. Попробуйте выбрать картинку через «Файлы» " +
                    "или введите ключ вручную.",
                    Toast.LENGTH_LONG).show()
            }
            return
        }

        scanner.process(InputImage.fromBitmap(bmp, 0))
            .addOnSuccessListener { list ->
                val raw = list.firstOrNull { it.rawValue != null }?.rawValue
                if (raw != null) deliver(raw)
                else Toast.makeText(this,
                    "QR-код не найден на изображении. Попробуйте другой файл или введите ключ вручную.",
                    Toast.LENGTH_LONG).show()
            }
            .addOnFailureListener {
                Toast.makeText(this, "Не удалось распознать изображение: ${it.message}",
                    Toast.LENGTH_LONG).show()
            }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_qr_scan)
        previewView = findViewById(R.id.previewView)
        txtStatus = findViewById(R.id.txtStatus)

        findViewById<Button>(R.id.btnFlip).setOnClickListener {
            lensFacing = if (lensFacing == CameraSelector.LENS_FACING_FRONT)
                CameraSelector.LENS_FACING_BACK else CameraSelector.LENS_FACING_FRONT
            bind()
        }
        findViewById<Button>(R.id.btnFromFile).setOnClickListener { pickImage() }
        findViewById<Button>(R.id.btnManual).setOnClickListener { setResult(RESULT_CANCELED); finish() }
        findViewById<Button>(R.id.btnCancel).setOnClickListener { setResult(RESULT_CANCELED); finish() }

        if (intent.getBooleanExtra(EXTRA_NO_CAMERA, false)) {
            cameraFailed("Нет доступа к камере")
            return
        }

        val future = ProcessCameraProvider.getInstance(this)
        future.addListener({
            try {
                provider = future.get()
                bind()
            } catch (e: Exception) {
                cameraFailed("Камера недоступна (${e.message ?: "ошибка инициализации"})")
            }
        }, ContextCompat.getMainExecutor(this))

        // Если долго не сканируется (далеко, блики, мелкий QR) — подсказать обходные пути
        mainHandler.postDelayed({
            if (!handled && !isFinishing) {
                Toast.makeText(this,
                    "Не сканируется? Нажмите «QR из файла» (пришлите PNG из бота на доску) или введите ключ вручную.",
                    Toast.LENGTH_LONG).show()
            }
        }, 25_000)
    }

    private fun bind() {
        val p = provider ?: return
        p.unbindAll()
        val preview = Preview.Builder().build().also { it.setSurfaceProvider(previewView.surfaceProvider) }
        @Suppress("DEPRECATION")
        val analysis = ImageAnalysis.Builder()
            .setTargetResolution(Size(1280, 720))
            .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
            .build()
        analysis.setAnalyzer(exec) { proxy -> analyze(proxy) }

        // Порядок: выбранная сторона → фронт → тыл → каждая физическая камера
        // (внешние USB-камеры досок не имеют LENS_FACING фронт/тыл — только полный перебор).
        val candidates = mutableListOf(
            CameraSelector.Builder().requireLensFacing(lensFacing).build(),
            CameraSelector.DEFAULT_FRONT_CAMERA,
            CameraSelector.DEFAULT_BACK_CAMERA)
        p.availableCameraInfos.forEach { candidates.add(it.cameraSelector) }

        for (sel in candidates) {
            try {
                val cam = p.bindToLifecycle(this, sel, preview, analysis)
                watchCameraState(cam.cameraInfo.cameraState)
                cameraOk = true
                txtStatus.text = "Наведите камеру на QR-код лицензии"
                return
            } catch (e: Exception) {}
        }
        // Старые HAL могут не тянуть preview+analysis вместе — пробуем без превью
        // (экран останется чёрным, но распознавание работает).
        for (sel in candidates) {
            try {
                val cam = p.bindToLifecycle(this, sel, analysis)
                watchCameraState(cam.cameraInfo.cameraState)
                cameraOk = true
                txtStatus.text = "Предпросмотр недоступен — просто наведите камеру на QR-код"
                return
            } catch (e: Exception) {}
        }
        cameraFailed("Камера недоступна")
    }

    /** Камера занята другим приложением/отвалилась уже после привязки. */
    private fun watchCameraState(state: androidx.lifecycle.LiveData<CameraState>) {
        state.observe(this) { s ->
            val err = s.error ?: return@observe
            val msg = when (err.code) {
                CameraState.ERROR_CAMERA_IN_USE, CameraState.ERROR_MAX_CAMERAS_IN_USE ->
                    "Камера занята другим приложением — закройте его и вернитесь"
                CameraState.ERROR_CAMERA_DISABLED ->
                    "Камера отключена политикой устройства"
                else -> "Сбой камеры (код ${err.code})"
            }
            if (!handled) cameraFailed(msg)
        }
    }

    /** Камеры нет/не работает: остаёмся на экране, работают «QR из файла» и ручной ввод. */
    private fun cameraFailed(reason: String) {
        cameraOk = false
        txtStatus.text = "$reason.\nНажмите «QR из файла» (пришлите PNG из бота на доску)\nили «Ввести ключ вручную»."
    }

    private fun deliver(raw: String) {
        if (handled) return
        handled = true
        setResult(RESULT_OK, Intent().putExtra("qr", raw))
        finish()
    }

    @OptIn(ExperimentalGetImage::class)
    private fun analyze(proxy: ImageProxy) {
        if (handled) { proxy.close(); return }
        val media = proxy.image ?: run { proxy.close(); return }
        val img = InputImage.fromMediaImage(media, proxy.imageInfo.rotationDegrees)
        scanner.process(img)
            .addOnSuccessListener { list ->
                val raw = list.firstOrNull { it.rawValue != null }?.rawValue
                if (raw != null) deliver(raw)
            }
            .addOnCompleteListener { proxy.close() }
    }

    override fun onDestroy() {
        super.onDestroy()
        mainHandler.removeCallbacksAndMessages(null)
        exec.shutdown()
        scanner.close()
    }
}
