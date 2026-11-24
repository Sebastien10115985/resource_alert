package com.kwg.resourcealart.data.network

import com.kwg.resourcealart.BuildConfig
import com.kwg.resourcealart.data.model.ChangePage
import com.kwg.resourcealart.data.model.Listing
import com.kwg.resourcealart.data.model.RecommendationPage
import com.kwg.resourcealart.data.model.Stats
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import retrofit2.Retrofit
import retrofit2.converter.kotlinx.serialization.asConverterFactory
import retrofit2.http.GET
import retrofit2.http.Path
import retrofit2.http.Query

interface ApiService {
    /** 每日优选列表，category=B/C，不传则返回全部 */
    @GET("api/recommendations")
    suspend fun recommendations(
        @Query("date") date: String? = null,
        @Query("category") category: String? = null,
        @Query("page") page: Int = 1,
        @Query("page_size") pageSize: Int = 50,
    ): RecommendationPage

    @GET("api/listings/{id}")
    suspend fun listingDetail(@Path("id") id: String): Listing

    @GET("api/changes")
    suspend fun changes(@Query("days") days: Int = 7): ChangePage

    @GET("api/stats")
    suspend fun stats(): Stats
}

object ApiClient {
    private val json = Json {
        ignoreUnknownKeys = true
        coerceInputValues = true
        isLenient = true
    }

    /** baseUrl 来自 BuildConfig（本地调试）；正式上线可切换为云服务域名 */
    val api: ApiService by lazy {
        Retrofit.Builder()
            .baseUrl(BuildConfig.API_BASE_URL + "/")
            .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
            .build()
            .create(ApiService::class.java)
    }
}
