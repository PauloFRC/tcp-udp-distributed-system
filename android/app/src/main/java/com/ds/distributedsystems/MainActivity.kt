package com.ds.distributedsystems

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.res.vectorResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.ds.distributedsystems.SensorData.DeviceType
import com.ds.distributedsystems.SensorData.SensorReading
import com.ds.distributedsystems.ui.theme.DistributedSystemsTheme
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import java.net.Socket
import java.nio.ByteBuffer
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

class MainActivity : ComponentActivity() {

    private val gatewayHost = "10.0.2.2"
    private val gatewayPort = 8082

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            DistributedSystemsTheme {
                Scaffold(modifier = Modifier.fillMaxSize()) { innerPadding ->
                    SensorDashboardScreen(
                        modifier = Modifier.padding(innerPadding)
                    )
                }
            }
        }
    }

    data class SensorData(
        val value: Double? = null,
        val unit: String = "",
        val timestamp: Long? = null
    )

    @Composable
    fun SensorDashboardScreen(modifier: Modifier = Modifier) {
        var selectedLocation by remember { mutableStateOf("Cocó") }
        val locations = listOf("Cocó", "Aldeota", "Iracema")

        var temperatureData by remember { mutableStateOf(SensorData()) }
        var humidityData by remember { mutableStateOf(SensorData()) }
        var status by remember { mutableStateOf("Waiting for data...") }

        LaunchedEffect(selectedLocation) {
            temperatureData = SensorData()
            humidityData = SensorData()
            status = "Se conectando aos dados da localização: $selectedLocation..."

            launch(Dispatchers.IO) {
                while (isActive) {
                    try {
                        Socket(gatewayHost, gatewayPort).use { socket ->
                            val outputStream = socket.getOutputStream()
                            val locationBytes = selectedLocation.toByteArray()
                            outputStream.write(locationBytes)
                            outputStream.flush()

                            val inputStream = socket.getInputStream()

                            while (true) {
                                val lengthBytes = ByteArray(4)
                                val readLen = inputStream.read(lengthBytes)
                                if (readLen != 4) {
                                    status = "Falha ao ler tamanho da mensagem."
                                    break
                                }

                                val length = ByteBuffer.wrap(lengthBytes).int
                                if (length == 0) {
                                    break
                                }

                                val dataBytes = ByteArray(length)
                                var bytesRead = 0
                                while (bytesRead < length) {
                                    val result = inputStream.read(dataBytes, bytesRead, length - bytesRead)
                                    if (result == -1) {
                                        status = "Fim inesperado da stream."
                                        break
                                    }
                                    bytesRead += result
                                }
                                if (bytesRead < length) {
                                    break
                                }

                                val reading = SensorReading.parseFrom(dataBytes)

                                if (reading.location == selectedLocation) {
                                    when (reading.sensorType) {
                                        DeviceType.TEMPERATURE -> {
                                            temperatureData = SensorData(reading.value, reading.unit, reading.timestamp)
                                        }
                                        DeviceType.HUMIDITY -> {
                                            humidityData = SensorData(reading.value, reading.unit, reading.timestamp)
                                        }
                                        else -> {
                                        }
                                    }
                                    status = "Última atualização: ${formatTimestamp(System.currentTimeMillis())}"
                                }
                            }
                        }
                    } catch (e: Exception) {
                        status = "Error: ${e.message}"
                        e.printStackTrace()
                    }
                    delay(5000)
                }
            }
        }

        Column(
            modifier = modifier
                .fillMaxSize()
                .padding(16.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Text(
                text = "Sistema de Cidade Inteligente",
                style = MaterialTheme.typography.headlineMedium,
                fontWeight = FontWeight.Bold
            )
            Spacer(modifier = Modifier.height(24.dp))

            LocationSelector(
                locations = locations,
                selectedLocation = selectedLocation,
                onLocationSelected = { newLocation ->
                    selectedLocation = newLocation
                }
            )
            Spacer(modifier = Modifier.height(24.dp))

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(16.dp)
            ) {
                SensorDisplayCard(
                    modifier = Modifier.weight(1f),
                    icon = ImageVector.vectorResource(id = R.drawable.thermostat),
                    title = "Temperatura",
                    data = temperatureData
                )
                SensorDisplayCard(
                    modifier = Modifier.weight(1f),
                    icon = ImageVector.vectorResource(id = R.drawable.droplet_solid),
                    title = "Umidade",
                    data = humidityData
                )
            }

            Spacer(modifier = Modifier.weight(1f))

            Text(
                text = status,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
    }

    @Composable
    fun LocationSelector(
        locations: List<String>,
        selectedLocation: String,
        onLocationSelected: (String) -> Unit
    ) {
        Row(
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            modifier = Modifier.padding(8.dp)
        ) {
            locations.forEach { location ->
                FilterChip(
                    selected = location == selectedLocation,
                    onClick = { onLocationSelected(location) },
                    label = { Text(text = location) }
                )
            }
        }
    }

    @Composable
    fun SensorDisplayCard(
        modifier: Modifier = Modifier,
        icon: ImageVector,
        title: String,
        data: SensorData
    ) {
        Card(
            modifier = modifier,
            shape = RoundedCornerShape(16.dp),
            elevation = CardDefaults.cardElevation(defaultElevation = 4.dp)
        ) {
            Column(
                modifier = Modifier
                    .padding(16.dp)
                    .fillMaxWidth()
                    .fillMaxHeight(),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.Center
            ) {
                Icon(
                    imageVector = icon,
                    contentDescription = title,
                    modifier = Modifier.size(40.dp),
                    tint = MaterialTheme.colorScheme.primary
                )
                Spacer(modifier = Modifier.height(8.dp))
                Text(
                    text = title,
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.SemiBold
                )
                Spacer(modifier = Modifier.height(8.dp))
                if (data.value != null) {
                    Text(
                        text = "${data.value} ${data.unit}",
                        style = MaterialTheme.typography.displaySmall,
                        fontWeight = FontWeight.Bold,
                        fontSize = 24.sp
                    )
                    Spacer(modifier = Modifier.height(4.dp))
                    Text(
                        text = "em ${formatTimestamp(data.timestamp)}",
                        style = MaterialTheme.typography.bodySmall,
                        fontSize = 10.sp
                    )
                } else {
                    Text(
                        text = "--",
                        style = MaterialTheme.typography.displaySmall,
                        color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.5f)
                    )
                }
            }
        }
    }

    private fun formatTimestamp(timestamp: Long?): String {
        if (timestamp == null) return "N/A"
        val sdf = SimpleDateFormat("HH:mm:ss", Locale.getDefault())
        return sdf.format(Date(timestamp))
    }
}
