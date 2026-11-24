package io.github.sirmeili.filamenttracker.push

import android.Manifest
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Bitmap
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import io.github.sirmeili.filamenttracker.MainActivity
import io.github.sirmeili.filamenttracker.R
import java.util.concurrent.atomic.AtomicInteger
import kotlin.concurrent.thread

/**
 * Shows a phone notification in its kind's channel. Tapping it opens the app at its page
 * ([EXTRA_PATH]); signed out, the web app asks to sign in first and then opens it. One with a
 * photo shows it as a large picture once downloaded ([PhotoDownloader]), or its text only if
 * the download fails.
 */
class Notifier(private val context: Context) {
    fun show(notification: PhoneNotification) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
            context.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
        ) {
            return
        }
        val photo = notification.photo
        if (photo == null) {
            post(notification, null)
        } else {
            // Off the caller's thread: a download may not run on the main thread.
            thread(name = "RollCallNotificationPhoto") { post(notification, PhotoDownloader(context).download(photo)) }
        }
    }

    private fun post(notification: PhoneNotification, picture: Bitmap?) {
        createChannels()
        val id = ids.incrementAndGet()
        val open =
            Intent(context, MainActivity::class.java)
                .putExtra(EXTRA_PATH, notification.path)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        val tap = PendingIntent.getActivity(context, id, open, PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        val built =
            NotificationCompat.Builder(context, NotificationChannels.of(notification.kind).id)
                .setSmallIcon(R.drawable.ic_rollcall_monochrome)
                .setContentTitle(notification.title)
                .setContentText(notification.text)
                .setStyle(
                    if (picture == null) {
                        NotificationCompat.BigTextStyle().bigText(notification.text)
                    } else {
                        // Expanded, the picture replaces the thumbnail beside the title.
                        NotificationCompat.BigPictureStyle()
                            .bigPicture(picture)
                            .bigLargeIcon(null as Bitmap?)
                            .setSummaryText(notification.text)
                    },
                )
                .apply { if (picture != null) setLargeIcon(picture) }
                .setContentIntent(tap)
                .setAutoCancel(true)
                .build()
        NotificationManagerCompat.from(context).notify(id, built)
    }

    private fun createChannels() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val manager = context.getSystemService(NotificationManager::class.java) ?: return
        NotificationChannels.ALL.forEach {
            manager.createNotificationChannel(NotificationChannel(it.id, it.name, NotificationManager.IMPORTANCE_DEFAULT))
        }
    }

    companion object {
        /** The page a tapped notification opens, on the intent that opens the app. */
        const val EXTRA_PATH = "io.github.sirmeili.rollcall.NOTIFICATION_PATH"

        // Each notification its own ID, so a new one never replaces an earlier one.
        private val ids = AtomicInteger((System.currentTimeMillis() and 0xFFFFFF).toInt())
    }
}
