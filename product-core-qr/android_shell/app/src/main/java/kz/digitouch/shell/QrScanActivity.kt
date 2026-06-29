package kz.digitouch.shell

import android.content.Intent
import android.os.Bundle
import android.util.Size
import android.widget.Button
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageProxy
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.core.content.ContextCompat
import com.google.zxing.BarcodeFormat
import com.google.zxing.BinaryBitmap
import com.google.zxing.DecodeHintType
import com.google.zxing.MultiFormatReader
import com.google.zxing.PlanarYUVLuminanceSource
import com.google.zxing.common.HybridBinarizer
import java.util.concurrent.Executors

/**
 * Сканер QR: CameraX (камера) + ZXing-core (декодер, лёгкий, офлайн).
 * По умолчанию ПЕРЕДНЯЯ камера (доска обращена в зал) + кнопка смены. Кадр 1280x720
 * — распознаёт с большей дистанции. Результат: Intent extra "qr".
 */
class QrScanActivity : AppCompatActivity() {

    private lateinit var previewView: PreviewView
    private val exec = Executors.newSingleThreadExecutor()
    private var provider: ProcessCameraProvider? = null
    private var lensFacing = CameraSelector.LENS_FACING_FRONT
    @Volatile private var handled = false

    private val reader = MultiFormatReader().apply {
        setHints(mapOf(
            DecodeHintType.POSSIBLE_FORMATS to listOf(BarcodeFormat.QR_CODE),
            DecodeHintType.TRY_HARDER to true
        ))
    }

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

    private fun analyze(proxy: ImageProxy) {
        if (handled) { proxy.close(); return }
        try {
            val plane = proxy.planes[0]
            val buf = plane.buffer
            val rowStride = plane.rowStride
            val needed = rowStride * proxy.height
            val data = ByteArray(needed)
            buf.get(data, 0, minOf(buf.remaining(), needed))
            val source = PlanarYUVLuminanceSource(
                data, rowStride, proxy.height, 0, 0, proxy.width, proxy.height, false)
            val text = reader.decodeWithState(BinaryBitmap(HybridBinarizer(source)))?.text
            if (text != null && !handled) {
                handled = true
                runOnUiThread { setResult(RESULT_OK, Intent().putExtra("qr", text)); finish() }
            }
        } catch (e: Exception) {
            // QR не найден в кадре — пропускаем
        } finally {
            reader.reset()
            proxy.close()
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        exec.shutdown()
    }
}