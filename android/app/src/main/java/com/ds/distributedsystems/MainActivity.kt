package com.ds.distributedsystems

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.ds.distributedsystems.SensorData.DeviceType
import com.ds.distributedsystems.SensorData.SensorReading
import com.ds.distributedsystems.ui.theme.DistributedSystemsTheme
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import java.net.Socket
import java.nio.ByteBuffer

class MainActivity : ComponentActivity() {

    private val gatewayHost = "10.0.2.2"
    private val gatewayPort = 8082

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            DistributedSystemsTheme {
                Scaffold(modifier = Modifier.fillMaxSize()) { _ ->
                    TemperatureScreen()
                }
            }
        }
    }

    @Composable
    fun TemperatureScreen() {
        val scope = rememberCoroutineScope()
        var temperature by remember { mutableStateOf<Double?>(null) }
        var location by remember { mutableStateOf("") }
        var unit by remember { mutableStateOf("") }
        var timestamp by remember { mutableStateOf<Long?>(null) }
        var status by remember { mutableStateOf("Waiting for data...") }

        LaunchedEffect(Unit) {
            scope.launch(Dispatchers.IO) {
                while (isActive) {
                    try {
                        Socket(gatewayHost, gatewayPort).use { socket ->
                            val lengthBytes = ByteArray(4)
                            if (socket.getInputStream().read(lengthBytes) != 4) {
                                status = "No data received."
                                delay(2000)
                                return@use
                            }
                            val length = ByteBuffer.wrap(lengthBytes).int
                            if (length == 0) {
                                status = "No temperature data available."
                                delay(2000)
                                return@use
                            }
                            val dataBytes = ByteArray(length)
                            var read = 0
                            while (read < length) {
                                val r = socket.getInputStream().read(dataBytes, read, length - read)
                                if (r == -1) break
                                read += r
                            }
                            val reading = SensorReading.parseFrom(dataBytes)
                            if (reading.sensorType == DeviceType.TEMPERATURE) {
                                temperature = reading.value
                                location = reading.location
                                unit = reading.unit
                                timestamp = reading.timestamp
                                status = "Data received from ${reading.sensorId}"
                            } else {
                                status = "Received non-temperature data."
                            }
                        }
                    } catch (e: Exception) {
                        status = "Error: ${e.localizedMessage}"
                    }
                    delay(5000)
                }
            }
        }

        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(24.dp),
            verticalArrangement = Arrangement.Center,
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Text(text = "Temperature Monitor", style = MaterialTheme.typography.titleLarge)
            Spacer(modifier = Modifier.height(16.dp))
            Text(text = "Status: $status")
            Spacer(modifier = Modifier.height(16.dp))
            temperature?.let {
                Text(text = "Temperature: $it $unit", style = MaterialTheme.typography.titleMedium)
            }
            Spacer(modifier = Modifier.height(8.dp))
            Text(text = "Location: $location")
            Spacer(modifier = Modifier.height(8.dp))
            timestamp?.let {
                Text(text = "Timestamp: $it")
            }
        }
    }
}
