package com.kwg.resourcealart.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.kwg.resourcealart.data.model.ChangeItem
import com.kwg.resourcealart.data.model.DailyRecommendations
import com.kwg.resourcealart.data.model.Listing
import com.kwg.resourcealart.data.network.ApiClient
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

data class UiState(
    val loading: Boolean = false,
    val daily: DailyRecommendations = DailyRecommendations("", emptyList(), emptyList()),
    val changes: List<ChangeItem> = emptyList(),
    val error: String? = null,
)

class MainViewModel : ViewModel() {
    private val _uiState = MutableStateFlow(UiState())
    val uiState: StateFlow<UiState> = _uiState.asStateFlow()

    init {
        refresh()
    }

    fun refresh() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(loading = true, error = null)
            try {
                val biz = ApiClient.api.recommendations(category = "B", pageSize = 50)
                val personal = ApiClient.api.recommendations(category = "C", pageSize = 50)
                val changes = ApiClient.api.changes(days = 7)
                _uiState.value = _uiState.value.copy(
                    loading = false,
                    daily = DailyRecommendations(
                        date = biz.date.ifEmpty { personal.date },
                        business = biz.items,
                        personal = personal.items,
                    ),
                    changes = changes.items,
                )
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    loading = false,
                    error = "连接服务端失败：${e.message ?: "未知错误"}\n请确认服务端已启动且 IP 配置正确",
                )
            }
        }
    }
}
