package com.ds.distributedsystems

import com.google.gson.annotations.SerializedName
import retrofit2.Response
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path

// --- 2. The Retrofit API Interface ---

interface GatewayApiService {
    @GET("devices")
    suspend fun getDevices(): Response<List<Device>>

    @GET("locations/{location_name}/devices")
    suspend fun getDevicesByLocation(@Path("location_name") location: String): Response<List<Device>>

    @GET("devices/{device_id}/data")
    suspend fun getOnDemandData(@Path("device_id") deviceId: String): Response<Device>

    @POST("devices/{device_id}/command")
    suspend fun sendCommand(
        @Path("device_id") deviceId: String,
        @Body payload: CommandPayload
    ): Response<Map<String, String>>
}

// --- 3. Singleton to provide the Retrofit instance ---

object RetrofitClient {
    private const val BASE_URL = "http://10.0.2.2:8000/"

    val instance: GatewayApiService by lazy {
        val retrofit = Retrofit.Builder()
            .baseUrl(BASE_URL)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
        retrofit.create(GatewayApiService::class.java)
    }
}