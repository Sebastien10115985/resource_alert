package com.kwg.resourcealart.ui.screen

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.kwg.resourcealart.data.model.ChangeItem

@Composable
fun ChangesScreen(changes: List<ChangeItem>) {
    val uriHandler = LocalUriHandler.current
    if (changes.isEmpty()) {
        Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
            Text("近 7 天无新增/降价/延期", color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        return
    }
    Column(Modifier.fillMaxSize()) {
        Text(
            "近 7 天变更（新增 / 降价 / 延期）",
            style = MaterialTheme.typography.titleMedium,
            fontWeight = FontWeight.Bold,
            modifier = Modifier.padding(14.dp),
        )
        LazyColumn(Modifier.fillMaxSize()) {
            items(changes, key = { it.id }) { c ->
                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 12.dp, vertical = 5.dp)
                        .clickable(enabled = c.url.isNotBlank()) {
                            try { uriHandler.openUri(c.url) } catch (_: Exception) { }
                        },
                ) {
                    Column(Modifier.padding(12.dp)) {
                        Text(c.title.ifBlank { "标的 ${c.listingId}" }, style = MaterialTheme.typography.bodyLarge)
                        Text(
                            "${c.field}：${c.old} → ${c.new}",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.primary,
                        )
                        Text(c.changedAt, style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
            }
        }
    }
}
