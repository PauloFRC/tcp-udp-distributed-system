package com.ds.distributedsystems

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExposedDropdownMenuBox
import androidx.compose.material3.ExposedDropdownMenuDefaults
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.LocalContentColor
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.res.vectorResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.ds.distributedsystems.SensorData.AppRequest
import com.ds.distributedsystems.SensorData.DeviceType
import com.ds.distributedsystems.SensorData.GatewayResponse
import com.ds.distributedsystems.SensorData.SensorReading
import com.ds.distributedsystems.ui.theme.DistributedSystemsTheme
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import java.io.DataInputStream
import java.io.DataOutputStream
import java.net.Socket
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

    data class DeviceData(
        val sensor_id: String = "",
        val value: Double? = null,
        val unit: String = "",
        val timestamp: Long? = null,
        val sensorType: DeviceType? = null
    )

    @Composable
    fun SensorDashboardScreen(modifier: Modifier = Modifier) {
        var selectedLocation by remember { mutableStateOf("Cocó") }
        val locations = listOf("Cocó", "Aldeota", "Iracema")

        var temperatureData by remember { mutableStateOf(DeviceData()) }
        var humidityData by remember { mutableStateOf(DeviceData()) }

        val allSensorReadings = remember { mutableStateMapOf<String, DeviceData>() }
        var allDevices by remember { mutableStateOf<List<SensorReading>>(emptyList()) }
        var selectedDeviceId by remember { mutableStateOf<String?>(null) }

        var status by remember { mutableStateOf("Esperando pelos dados...") }

        LaunchedEffect(selectedLocation) {
            temperatureData = DeviceData()
            humidityData = DeviceData()
            status = "Se conectando aos dados da localização: $selectedLocation..."

            launch(Dispatchers.IO) {
                while (isActive) {
                    try {
                        val request = AppRequest.newBuilder()
                            .setType(AppRequest.RequestType.STREAM_LOCATION_DATA)
                            .setStreamRequest(AppRequest.StreamLocationRequest.newBuilder().setLocationName(selectedLocation))
                            .build()

                        Socket(gatewayHost, gatewayPort).use { socket ->
                            val output = DataOutputStream(socket.outputStream)
                            val input = DataInputStream(socket.inputStream)

                            val requestBytes = request.toByteArray()
                            output.writeInt(requestBytes.size)
                            output.write(requestBytes)
                            output.flush()

                            while (isActive) {
                                val len = input.readInt()
                                if (len == 0) break
                                val responseBytes = ByteArray(len)
                                input.readFully(responseBytes)
                                val response = GatewayResponse.parseFrom(responseBytes)

                                if (response.type == GatewayResponse.ResponseType.SINGLE_READING) {
                                    val reading = response.singleReading
                                    val deviceData = DeviceData(reading.sensorId, reading.value, reading.unit, reading.timestamp, reading.sensorType)
                                    allSensorReadings[reading.sensorId] = deviceData

                                    if (reading.location == selectedLocation) {
                                        when (reading.sensorType) {
                                            DeviceType.TEMPERATURE -> temperatureData = deviceData
                                            DeviceType.HUMIDITY -> humidityData = deviceData
                                            else -> {}
                                        }
                                    }
                                }
                            }
                            status = "Última atualização: ${formatTimestamp(System.currentTimeMillis())}"
                        }
                    } catch (e: Exception) {
                        status = "Error: ${e.message}"
                    }
                    delay(5000)
                }
            }
        }

        LaunchedEffect(Unit) {
            launch(Dispatchers.IO) {
                while(isActive) {
                    try {
                        val request = AppRequest.newBuilder().setType(AppRequest.RequestType.LIST_DEVICES).build()
                        Socket(gatewayHost, gatewayPort).use { socket ->
                            val output = DataOutputStream(socket.outputStream)
                            val input = DataInputStream(socket.inputStream)

                            val requestBytes = request.toByteArray()
                            output.writeInt(requestBytes.size)
                            output.write(requestBytes)
                            output.flush()

                            val len = input.readInt()
                            if (len > 0) {
                                val responseBytes = ByteArray(len)
                                input.readFully(responseBytes)
                                val response = GatewayResponse.parseFrom(responseBytes)
                                if (response.type == GatewayResponse.ResponseType.DEVICE_LIST) {
                                    allDevices = response.deviceList.devicesList
                                    if (selectedDeviceId != null && allDevices.none { it.sensorId == selectedDeviceId }) {
                                        selectedDeviceId = null
                                    }
                                }
                            }
                        }
                    } catch (e: Exception) {
                        e.printStackTrace()
                        allDevices = emptyList()
                        selectedDeviceId = null
                    }
                    delay(10000L) // Atualiza a cada 10 segundos
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
            Spacer(modifier = Modifier.height(8.dp))

            LocationSelector(
                locations = locations,
                selectedLocation = selectedLocation,
                onLocationSelected = { newLocation ->
                    selectedLocation = newLocation
                }
            )
            Spacer(modifier = Modifier.height(8.dp))

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

            Spacer(Modifier.height(10.dp))
            Text("Inspecionar Dispositivo", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
            Spacer(Modifier.height(10.dp))

            DeviceSelector(
                devices = allDevices,
                selectedDeviceId = selectedDeviceId,
                onDeviceSelected = { deviceId -> selectedDeviceId = deviceId }
            )

            AnimatedVisibility(visible = selectedDeviceId != null) {
                val selectedDevice = allDevices.find { it.sensorId == selectedDeviceId }
                selectedDevice?.let {
                    DeviceReadingComponent(
                        deviceInfo = it,
                        latestUdpData = allSensorReadings[it.sensorId]
                    )
                }
            }

            Spacer(modifier = Modifier.weight(1f))

            Text(
                text = status,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
    }

    @OptIn(ExperimentalMaterial3Api::class)
    @Composable
    fun DeviceSelector(
        devices: List<SensorReading>,
        selectedDeviceId: String?,
        onDeviceSelected: (String) -> Unit
    ) {
        var expanded by remember { mutableStateOf(false) }
        ExposedDropdownMenuBox(
            expanded = expanded,
            onExpandedChange = { expanded = !expanded }
        ) {
            OutlinedTextField(
                value = selectedDeviceId ?: "Select a device...",
                onValueChange = {},
                readOnly = true,
                trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = expanded) },
                modifier = Modifier.menuAnchor().fillMaxWidth()
            )
            ExposedDropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
                devices.forEach { deviceInfo ->
                    DropdownMenuItem(
                        text = { Text(deviceInfo.sensorId) },
                        onClick = {
                            onDeviceSelected(deviceInfo.sensorId)
                            expanded = false
                        }
                    )
                }
            }
        }
    }

    @Composable
    fun DeviceReadingComponent(deviceInfo: SensorReading, latestUdpData: DeviceData?) {
        val scope = rememberCoroutineScope()
        var tcpData by remember { mutableStateOf<DeviceData?>(null) }
        var requestStatus by remember { mutableStateOf("") }

        LaunchedEffect(deviceInfo.sensorId) {
            tcpData = null
            requestStatus = ""
        }

        // Usa ultima dado TCP como display, se não houver usa ultima atualização
        val displayData = tcpData ?: latestUdpData ?: DeviceData(deviceInfo.sensorId, deviceInfo.value,
            deviceInfo.unit, deviceInfo.timestamp, deviceInfo.sensorType)

        fun sendDeviceCommand(command: String) {
            scope.launch(Dispatchers.IO) {
                requestStatus = "Enviando '$command'..."
                try {
                    val commandProto = SensorData.DeviceCommand.newBuilder().setTargetId(deviceInfo.sensorId).setCommand(command).build()
                    val request = AppRequest.newBuilder().setType(AppRequest.RequestType.QUEUE_COMMAND).setCommandRequest(commandProto).build()

                    Socket(gatewayHost, gatewayPort).use { socket ->
                        val output = DataOutputStream(socket.outputStream)
                        val input = DataInputStream(socket.inputStream)

                        val requestBytes = request.toByteArray()
                        output.writeInt(requestBytes.size)
                        output.write(requestBytes)
                        output.flush()

                        val len = input.readInt()
                        if (len > 0) {
                            val responseBytes = ByteArray(len)
                            input.readFully(responseBytes)
                            val response = GatewayResponse.parseFrom(responseBytes)
                            if (response.type == GatewayResponse.ResponseType.COMMAND_CONFIRMATION) {
                                requestStatus = response.confirmationMessage
                            }
                        }
                    }
                } catch (e: Exception) {
                    requestStatus = "Erro: ${e.message}"
                }
            }
        }

        Card(
            modifier = Modifier.fillMaxWidth().padding(top = 16.dp),
            elevation = CardDefaults.cardElevation(2.dp),
            shape = RoundedCornerShape(12.dp)
        ) {
            Column(Modifier.padding(16.dp).fillMaxWidth(), horizontalAlignment = Alignment.CenterHorizontally) {
                Text(text = deviceInfo.sensorId, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                Spacer(Modifier.height(10.dp))

                Text(
                    "${displayData.value} ${displayData.unit}",
                    style = MaterialTheme.typography.headlineMedium,
                    color = if (tcpData != null) MaterialTheme.colorScheme.primary else LocalContentColor.current
                )
                Text(
                    "em ${formatTimestamp(displayData.timestamp)}",
                    style = MaterialTheme.typography.bodySmall
                )

                Spacer(Modifier.height(10.dp))

                Button(onClick = {
                    scope.launch(Dispatchers.IO) {
                        requestStatus = "Requisitando dados..."
                        try {
                            val onDemandReq = AppRequest.OnDemandRequest.newBuilder().setDeviceId(deviceInfo.sensorId).build()
                            val request = AppRequest.newBuilder().setType(AppRequest.RequestType.GET_ON_DEMAND_DATA).setOnDemandRequest(onDemandReq).build()

                            Socket(gatewayHost, gatewayPort).use { socket ->
                                val output = DataOutputStream(socket.outputStream)
                                val input = DataInputStream(socket.inputStream)

                                val requestBytes = request.toByteArray()
                                output.writeInt(requestBytes.size)
                                output.write(requestBytes)
                                output.flush()

                                val len = input.readInt()
                                if (len > 0) {
                                    val responseBytes = ByteArray(len)
                                    input.readFully(responseBytes)
                                    val response = GatewayResponse.parseFrom(responseBytes)
                                    if (response.type == GatewayResponse.ResponseType.SINGLE_READING) {
                                        val reading = response.singleReading
                                        tcpData = DeviceData(reading.sensorId, reading.value, reading.unit, reading.timestamp, reading.sensorType)
                                        requestStatus = "Leitura TCP atualizada"
                                    }
                                } else {
                                    requestStatus = "Timeout no gateway."
                                }
                            }
                        } catch (e: Exception) {
                            requestStatus = "Erro: ${e.message}"
                        }
                    }
                }) {
                    Text("Requisitar leitura (TCP)")
                }

                when (displayData.sensorType) {
                    DeviceType.SEMAPHORE -> {
                        Button(onClick = { sendDeviceCommand("vermelho") }) {
                            Text("Fechar semáforo")
                        }
                    }

                    DeviceType.LAMP_POST -> {
                        Row(horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                            Button(onClick = { sendDeviceCommand("on") }) { Text("ON") }
                            Button(onClick = { sendDeviceCommand("off") }) { Text("OFF") }
                        }
                    }

                    DeviceType.UNKNOWN -> {}
                    DeviceType.TEMPERATURE -> {}
                    DeviceType.HUMIDITY -> {}
                    DeviceType.ALARM -> {}
                    DeviceType.UNRECOGNIZED -> {}
                    null -> {}
                }

                if (requestStatus.isNotEmpty()) {
                    Text(requestStatus, style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(top = 8.dp))
                }
            }
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
        data: DeviceData
    ) {
        Card(
            modifier = modifier,
            shape = RoundedCornerShape(16.dp),
            elevation = CardDefaults.cardElevation(defaultElevation = 4.dp)
        ) {
            Column(
                modifier = Modifier
                    .padding(16.dp)
                    .fillMaxWidth(),
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
