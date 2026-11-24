package com.kwg.resourcealart.data.model

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/**
 * 统一标的数据模型，与服务端 listings 表 / 开发文档 §4.1 Schema 对齐。
 * category: B=企业类, C=个人类, BC=双推（服务端在 B/C 两组各返回一条，App 无需区分）
 */
@Serializable
data class Listing(
    val id: String = "",
    val source: String = "",
    @SerialName("external_id") val externalId: String = "",
    val category: String = "C",
    @SerialName("asset_type") val assetType: String = "",
    val title: String = "",
    val province: String = "",
    val city: String = "",
    val district: String = "",
    @SerialName("area_sqm") val areaSqm: Double? = null,
    @SerialName("price_yuan") val priceYuan: Double? = null,
    @SerialName("price_text") val priceText: String = "",
    @SerialName("appraisal_yuan") val appraisalYuan: Double? = null,
    @SerialName("unit_price") val unitPrice: Double? = null,
    @SerialName("discount_rate") val discountRate: Double? = null,
    val deadline: String = "",
    val seller: String = "",
    @SerialName("seller_grade") val sellerGrade: String = "",
    @SerialName("second_listing") val secondListing: Boolean = false,
    @SerialName("use_type") val useType: String = "",
    val url: String = "",
    @SerialName("published_at") val publishedAt: String = "",
    @SerialName("collected_at") val collectedAt: String = "",
    val score: Int = 0,
    @SerialName("score_reasons") val scoreReasons: List<String> = emptyList(),
)

/** /api/recommendations 的分页响应 */
@Serializable
data class RecommendationPage(
    val date: String = "",
    val items: List<Listing> = emptyList(),
    val total: Int = 0,
    val page: Int = 1,
)

/** 今日展示给用户的两类数据 */
data class DailyRecommendations(
    val date: String,
    val business: List<Listing>,
    val personal: List<Listing>,
)

/** 单条变更记录 */
@Serializable
data class ChangeItem(
    val id: String = "",
    @SerialName("listing_id") val listingId: String = "",
    val field: String = "",
    val old: String = "",
    val new: String = "",
    @SerialName("changed_at") val changedAt: String = "",
    val title: String = "",
    val url: String = "",
)

@Serializable
data class ChangePage(
    val items: List<ChangeItem> = emptyList(),
    val total: Int = 0,
)

/** /api/stats 各平台采集状态 */
@Serializable
data class SourceStat(
    val name: String = "",
    @SerialName("last_run") val lastRun: String = "",
    val status: String = "",
    @SerialName("item_count") val itemCount: Int = 0,
)

@Serializable
data class Stats(
    val sources: List<SourceStat> = emptyList(),
    val today: Int = 0,
)
