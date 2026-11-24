package com.kwg.resourcealart.ui.screen

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.SecondaryTabRow
import androidx.compose.material3.Tab
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.kwg.resourcealart.data.model.DailyRecommendations

@Composable
fun DailyScreen(daily: DailyRecommendations, loading: Boolean, error: String?) {
    var tab by remember { mutableIntStateOf(0) }
    val tabs = listOf("企业类", "个人类")
    val items = if (tab == 0) daily.business else daily.personal

    Column(Modifier.fillMaxSize()) {
        SecondaryTabRow(selectedTabIndex = tab) {
            tabs.forEachIndexed { index, name ->
                Tab(
                    selected = tab == index,
                    onClick = { tab = index },
                    text = { Text("$name (${if (index == 0) daily.business.size else daily.personal.size})") },
                )
            }
        }

        when {
            loading -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                CircularProgressIndicator()
            }
            error != null -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Text(
                    text = error,
                    color = MaterialTheme.colorScheme.error,
                    textAlign = TextAlign.Center,
                    modifier = Modifier.padding(24.dp),
                )
            }
            items.isEmpty() -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Text("暂无数据，请先运行服务端采集", color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            else -> {
                Text(
                    text = "${daily.date} 优选 · 按评分排序 · 点卡片打开原始公告",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(horizontal = 14.dp, vertical = 8.dp),
                )
                HorizontalDivider()
                LazyColumn(Modifier.fillMaxSize()) {
                    items(items, key = { it.id }) { listing -> ListingCard(listing) }
                }
            }
        }
    }
}
