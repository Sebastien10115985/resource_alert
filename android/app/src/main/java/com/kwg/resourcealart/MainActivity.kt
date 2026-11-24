package com.kwg.resourcealart

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.viewModels
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AutoAwesome
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.Update
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.kwg.resourcealart.ui.screen.ChangesScreen
import com.kwg.resourcealart.ui.screen.DailyScreen
import com.kwg.resourcealart.ui.screen.ProfileScreen
import com.kwg.resourcealart.ui.theme.ResourceAlertTheme
import com.kwg.resourcealart.viewmodel.MainViewModel

class MainActivity : ComponentActivity() {
    private val vm: MainViewModel by viewModels()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            ResourceAlertTheme {
                AppRoot(vm)
            }
        }
    }
}

private data class NavItem(val label: String, val icon: ImageVector)

@Composable
private fun AppRoot(vm: MainViewModel) {
    val state by vm.uiState.collectAsStateWithLifecycle()
    val items = listOf(
        NavItem("每日优选", Icons.Filled.AutoAwesome),
        NavItem("变更", Icons.Filled.Update),
        NavItem("我的", Icons.Filled.Person),
    )
    var selectedIndex by remember { mutableIntStateOf(0) }

    Scaffold(
        bottomBar = {
            NavigationBar {
                items.forEachIndexed { index, item ->
                    NavigationBarItem(
                        selected = selectedIndex == index,
                        onClick = { selectedIndex = index },
                        icon = { Icon(item.icon, contentDescription = item.label) },
                        label = { Text(item.label) },
                    )
                }
            }
        }
    ) { pad ->
        androidx.compose.foundation.layout.Box(Modifier.padding(pad)) {
            when (selectedIndex) {
                0 -> DailyScreen(state.daily, state.loading, state.error)
                1 -> ChangesScreen(state.changes)
                2 -> ProfileScreen(onRefresh = { vm.refresh() })
            }
        }
    }
}
