package uz.jarvis.mobile

import android.Manifest
import android.annotation.SuppressLint
import android.app.Activity
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Color
import android.media.AudioAttributes
import android.media.MediaPlayer
import android.net.Uri
import android.os.Bundle
import android.speech.tts.TextToSpeech
import android.util.Base64
import android.webkit.JavascriptInterface
import android.webkit.PermissionRequest
import android.webkit.ValueCallback
import android.webkit.WebChromeClient
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import java.io.File
import java.util.Locale

class MainActivity : AppCompatActivity(), TextToSpeech.OnInitListener {

    private lateinit var webView: WebView
    private var tts: TextToSpeech? = null
    private var ttsReady = false
    private var mediaPlayer: MediaPlayer? = null
    private var fileCallback: ValueCallback<Array<Uri>>? = null

    private val filePicker = registerForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) { result ->
        val uris = if (result.resultCode == Activity.RESULT_OK) {
            val data = result.data
            when {
                data?.data != null -> arrayOf(data.data!!)
                data?.clipData != null -> Array(data.clipData!!.itemCount) { i ->
                    data.clipData!!.getItemAt(i).uri
                }
                else -> null
            }
        } else null
        fileCallback?.onReceiveValue(uris)
        fileCallback = null
    }

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.statusBarColor = Color.parseColor("#050a14")
        window.navigationBarColor = Color.parseColor("#050a14")

        requestRuntimePermissions()
        tts = TextToSpeech(this, this)

        webView = WebView(this)
        setContentView(webView)

        webView.setBackgroundColor(Color.parseColor("#050a14"))
        webView.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
            databaseEnabled = true
            mediaPlaybackRequiresUserGesture = false
            allowFileAccess = true
            allowContentAccess = true
            mixedContentMode = WebSettings.MIXED_CONTENT_ALWAYS_ALLOW
            useWideViewPort = true
            loadWithOverviewMode = true
        }

        webView.addJavascriptInterface(AndroidBridge(), "JarvisAndroid")
        webView.webViewClient = WebViewClient()
        webView.webChromeClient = object : WebChromeClient() {
            override fun onPermissionRequest(request: PermissionRequest) {
                runOnUiThread { request.grant(request.resources) }
            }

            override fun onShowFileChooser(
                view: WebView?,
                callback: ValueCallback<Array<Uri>>?,
                params: FileChooserParams?
            ): Boolean {
                fileCallback?.onReceiveValue(null)
                fileCallback = callback
                val intent = params?.createIntent() ?: Intent(Intent.ACTION_GET_CONTENT).apply {
                    addCategory(Intent.CATEGORY_OPENABLE)
                    type = "image/*"
                }
                return try {
                    filePicker.launch(intent)
                    true
                } catch (_: Exception) {
                    fileCallback = null
                    false
                }
            }
        }

        webView.loadUrl("file:///android_asset/www/index.html")
    }

    private fun requestRuntimePermissions() {
        val needed = arrayOf(
            Manifest.permission.RECORD_AUDIO,
            Manifest.permission.CAMERA
        ).filter {
            ContextCompat.checkSelfPermission(this, it) != PackageManager.PERMISSION_GRANTED
        }
        if (needed.isNotEmpty()) {
            ActivityCompat.requestPermissions(this, needed.toTypedArray(), 1001)
        }
    }

    override fun onInit(status: Int) {
        if (status == TextToSpeech.SUCCESS) {
            val uz = Locale("uz", "UZ")
            val res = tts?.setLanguage(uz)
            if (res == TextToSpeech.LANG_MISSING_DATA || res == TextToSpeech.LANG_NOT_SUPPORTED) {
                val ru = tts?.setLanguage(Locale("ru", "RU"))
                if (ru == TextToSpeech.LANG_MISSING_DATA || ru == TextToSpeech.LANG_NOT_SUPPORTED) {
                    tts?.setLanguage(Locale.getDefault())
                }
            }
            ttsReady = true
        }
    }

    private fun stopNativeAudio() {
        try {
            mediaPlayer?.stop()
        } catch (_: Exception) {}
        try {
            mediaPlayer?.release()
        } catch (_: Exception) {}
        mediaPlayer = null
    }

    inner class AndroidBridge {
        @JavascriptInterface
        fun speak(text: String): Boolean {
            if (!ttsReady) return false
            runOnUiThread {
                stopNativeAudio()
                tts?.speak(text.take(700), TextToSpeech.QUEUE_FLUSH, null, "jarvis-utterance")
            }
            return true
        }

        @JavascriptInterface
        fun playBase64Audio(b64: String, ext: String): Boolean {
            return try {
                val bytes = Base64.decode(b64, Base64.DEFAULT)
                val safeExt = if (ext == "mp3" || ext == "ogg") ext else "wav"
                val tmp = File(cacheDir, "jarvis_reply.$safeExt")
                tmp.writeBytes(bytes)
                runOnUiThread {
                    try {
                        tts?.stop()
                        stopNativeAudio()
                        val mp = MediaPlayer()
                        mp.setAudioAttributes(
                            AudioAttributes.Builder()
                                .setUsage(AudioAttributes.USAGE_MEDIA)
                                .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                                .build()
                        )
                        mp.setDataSource(tmp.absolutePath)
                        mp.setOnCompletionListener { stopNativeAudio() }
                        mp.setOnErrorListener { _, _, _ -> stopNativeAudio(); true }
                        mp.prepare()
                        mp.start()
                        mediaPlayer = mp
                    } catch (_: Exception) {
                        stopNativeAudio()
                    }
                }
                true
            } catch (_: Exception) {
                false
            }
        }

        @JavascriptInterface
        fun stopSpeaking() {
            runOnUiThread {
                tts?.stop()
                stopNativeAudio()
            }
        }
    }

    override fun onDestroy() {
        tts?.stop()
        tts?.shutdown()
        stopNativeAudio()
        super.onDestroy()
    }
}
