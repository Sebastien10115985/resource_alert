package com.kwg.resourcealart.ui.theme

import android.app.Activity
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.SideEffect
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.platform.LocalView

private val LightColors = lightColorScheme(
    primary = Color(0xFF1565C0),
    onPrimary = Color.White,
    primaryContainer = Color(0xFFBBDEFB),
    secondary = Color(0xFF00897B),
    background = Color(0xFFFAFAFA),
    surface = Color.White,
    error = Color(0xFFC62828),
)

private val DarkColors = darkColorScheme(
    primary = Color(0xFF90CAF9),
    onPrimary = Color(0xFF0D47A1),
    primaryContainer = Color(0xFF1565C0),
    secondary = Color(0xFF4DB6AC),
    background = Color(0xFF121212),
    surface = Color(0xFF1E1E1E),
    error = Color(0xFFEF9A9A),
)

@Composable
fun ResourceAlertTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit,
) {
    val colorScheme = if (darkTheme) DarkColors else LightColors
    val view = LocalView.current
    if (!view.isInEditMode) {
        SideEffect {
            (view.context as? Activity)?.window?.statusBarColor = colorScheme.primary.toArgb()
        }
    }
    MaterialTheme(
        colorScheme = colorScheme,
        typography = Typography,
        content = content,
    )
}
