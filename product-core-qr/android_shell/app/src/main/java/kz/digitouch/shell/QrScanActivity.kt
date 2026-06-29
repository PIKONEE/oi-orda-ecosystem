package kz.digitouch.shell

import android.content.Intent
import android.os.Bundle
import android.util.Size
import android.widget.Button
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.camera.core.CameraSelector
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
 * Сканер QR: CameraX + ML Kit (надёжное распознавание, модель вшита/офлайн).
 * Передняя камера по умолчанию + кнопка смены. Кадр 1280x720 — больше дистанция.
 */
class QrScanActivity : AppCompatActivity() {

    private lateinit var previewView: PreviewView
    private val exec = Executors.newSingleThreadExecutor()
    private var provider: ProcessCameraProvider? = null
    private var lensFacing = CameraSelector.LENS_FACING_FRONT
    @Volatile private var handled = false

    private val scanner = BarcodeScanning.getClient(
        BarcodeScannerOptions.Builder().setBarcodeFormats(Barcode.FORMAT_QR_CODE).build())

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_qr_scan)
        previewView = findViewById(R.id.previewView)
        findViewById<Button>(R.id.btnFlip).setOnClickListener {
            lensFacing = if (lensFacing == CameraSelector.LENS_FACING_FRONT)
                CameraSelector.LENS_FACING_BACK else CameraSelector.LENS_FACING_FRONT
            bind()
        }
        findViewById<Button>(R.id.btnCancel).setOnClickListener { setResult(RESULT_CANCELED); finish() }
        val future = ProcessCameraProvider.getInstance(this)
        future.addListener({ provider = future.get(); bind() }, ContextCompat.getMainExecutor(this))
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
        val want = CameraSelector.Builder().requireLensFacing(lensFacing).build()
        for (sel in listOf(want, CameraSelector.DEFAULT_FRONT_CAMERA, CameraSelector.DEFAULT_BACK_CAMERA)) {
            try { p.bindToLifecycle(this, sel, preview, analysis); return } catch (e: Exception) {}
        }
        Toast.makeText(this, "Камера недоступна", Toast.LENGTH_LONG).show()
    }

    @OptIn(ExperimentalGetImage::class)
    private fun analyze(proxy: ImageProxy) {
        if (handled) { proxy.close(); return }
        val media = proxy.image ?: run { proxy.close(); return }
        val img = InputImage.fromMediaImage(media, proxy.imageInfo.rotationDegrees)
        scanner.process(img)
            .addOnSuccessListener { list ->
                val raw = list.firstOrNull { it.rawValue != null }?.rawValue
                if (raw != null && !handled) {
                    handled = true
                    setResult(RESULT_OK, Intent().putExtra("qr", raw))
                    finish()
                }
            }
            .addOnCompleteListener { proxy.close() }
    }

    override fun onDestroy() {
        super.onDestroy()
        exec.shutdown()
        scanner.close()
    }
}