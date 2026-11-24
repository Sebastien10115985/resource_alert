package com.kwg.resourcealart.ui.screen

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.SuggestionChip
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.kwg.resourcealart.data.model.Listing

/** 评分颜色：高分红（中国习惯：好/涨=红），低分灰 */
@Composable
private fun scoreColor(score: Int) = when {
    score >= 70 -> androidx.compose.ui.graphics.Color(0xFFC62828)
    score >= 40 -> androidx.compose.ui.graphics.Color(0xFFEF6C00)
    else -> MaterialTheme.colorScheme.onSurfaceVariant
}

@Composable
fun ListingCard(listing: Listing) {
    val uriHandler = LocalUriHandler.current
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 12.dp, vertical = 5.dp)
            .clickable(enabled = listing.url.isNotBlank()) {
                try { uriHandler.openUri(listing.url) } catch (_: Exception) { }
            },
        shape = RoundedCornerShape(12.dp),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp),
    ) {
        Column(Modifier.padding(14.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    text = "[${listing.score}分]",
                    color = scoreColor(listing.score),
                    fontWeight = FontWeight.Bold,
                    style = MaterialTheme.typography.labelLarge,
                )
                Spacer(Modifier.width(8.dp))
                Text(
                    text = "${listing.assetType} · ${listing.city}${if (listing.district.isNotBlank()) "/${listing.district}" else ""}",
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Spacer(Modifier.width(8.dp))
                if (listing.source.isNotBlank()) {
                    SuggestionChip(
                        onClick = {},
                        label = { Text(listing.source, style = MaterialTheme.typography.labelSmall) },
                    )
                }
            }
            Spacer(Modifier.height(6.dp))
            Text(
                text = listing.title,
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
            )
            Spacer(Modifier.height(6.dp))
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    text = listing.priceText.ifBlank { "价格面议" },
                    color = MaterialTheme.colorScheme.primary,
                    fontWeight = FontWeight.Bold,
                    style = MaterialTheme.typography.bodyMedium,
                )
                listing.unitPrice?.let {
                    Text(
                        text = "  ·  ${it.toInt()}元/㎡",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                listing.discountRate?.let { d ->
                    if (d > 0 && d < 1) {
                        Text(
                            text = "  ·  ${((1 - d) * 100).toInt()}%低于评估",
                            style = MaterialTheme.typography.bodySmall,
                            color = scoreColor(90),
                        )
                    }
                }
            }
            if (listing.scoreReasons.isNotEmpty()) {
                Spacer(Modifier.height(6.dp))
                Text(
                    text = "理由：${listing.scoreReasons.joinToString(" · ")}",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                )
            }
        }
    }
}
