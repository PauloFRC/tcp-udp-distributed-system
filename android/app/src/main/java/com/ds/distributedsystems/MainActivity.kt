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
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Warning
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
import com.ds.distributedsystems.ui.theme.DistributedSystemsTheme
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import com.google.gson.annotations.SerializedName
import com.ds.distributedsystems.R

data class Device(
    val sensor_id: String,
    val value: Double,
    val unit: String,
    val timestamp: Long,
    @SerializedName("sensor_type") val sensorType: String,
    val location: String,
    val metadata: Map<String, String>
)

data class CommandPayload(
    val command: String,
    val params: Map<String, Any>? = null
)

class MainActivity : ComponentActivity() {
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
        val sensorType: String = "UNKNOWN"
    )

    @Composable
    fun SensorDashboardScreen(modifier: Modifier = Modifier) {
        var selectedLocation by remember { mutableStateOf("Cocó") }
        val locations = listOf("Cocó", "Aldeota", "Iracema")

        var temperatureData by remember { mutableStateOf(DeviceData()) }
        var humidityData by remember { mutableStateOf(DeviceData()) }

        var allDevices by remember { mutableStateOf<List<Device>>(emptyList()) }
        var selectedDeviceId by remember { mutableStateOf<String?>(null) }

        val activeAlarms = remember { mutableStateMapOf<String, String>() }
        var status by remember { mutableStateOf("Esperando pelos dados...") }
        val apiService = RetrofitClient.instance

        LaunchedEffect(selectedLocation) {
            temperatureData = DeviceData()
            humidityData = DeviceData()
            status = "Se conectando aos dados da localização: $selectedLocation..."

            launch(Dispatchers.IO) {
                while (isActive) {
                    try {
                        val response = apiService.getDevicesByLocation(selectedLocation)
                        if (response.isSuccessful) {
                            val devicesInLocation = response.body() ?: emptyList()
                            devicesInLocation.forEach { device ->
                                val deviceData = DeviceData(device.sensor_id, device.value, device.unit, device.timestamp, device.sensorType)
                                when (device.sensorType) {
                                    "TEMPERATURE" -> temperatureData = deviceData
                                    "HUMIDITY" -> humidityData = deviceData
                                    else -> {}
                                }
                            }
                            status = "Última atualização: ${formatTimestamp(System.currentTimeMillis())}"
                        } else {
                            status = "Erro ao buscar dados: ${response.code()}"
                        }
                    } catch (e: Exception) {
                        status = "Error: ${e.message}"
                    }
                    delay(3000) // Poll every 3 seconds
                }
            }
        }

        LaunchedEffect(Unit) {
            launch(Dispatchers.IO) {
                while(isActive) {
                    try {
                        val response = apiService.getDevices()
                        if (response.isSuccessful) {
                            allDevices = response.body() ?: emptyList()

                            val newActiveAlarms = mutableMapOf<String, String>()
                            allDevices.forEach { device ->
                                if (device.sensorType == "ALARM" && device.value == 1.0) {
                                    newActiveAlarms[device.sensor_id] = device.location
                                }
                            }
                            activeAlarms.clear()
                            activeAlarms.putAll(newActiveAlarms)

                            if (selectedDeviceId != null && allDevices.none { it.sensor_id == selectedDeviceId }) {
                                selectedDeviceId = null
                            }
                        } else {
                            allDevices = emptyList()
                            selectedDeviceId = null
                        }
                    } catch (e: Exception) {
                        e.printStackTrace()
                        allDevices = emptyList()
                        selectedDeviceId = null
                    }
                    delay(3000L) // Poll every 3 seconds
                }
            }
        }

        val scrollState = rememberScrollState()

        Column(
            modifier = modifier
                .fillMaxSize()
                .verticalScroll(scrollState)
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

            AlarmWarningSection(activeAlarms = activeAlarms)

            Spacer(Modifier.height(10.dp))
            Text("Inspecionar Dispositivo", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
            Spacer(Modifier.height(10.dp))

            DeviceSelector(
                devices = allDevices,
                selectedDeviceId = selectedDeviceId,
                onDeviceSelected = { deviceId -> selectedDeviceId = deviceId }
            )

            AnimatedVisibility(visible = selectedDeviceId != null) {
                val selectedDevice = allDevices.find { it.sensor_id == selectedDeviceId }
                selectedDevice?.let {
                    DeviceReadingComponent(deviceInfo = it)
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

    @Composable
    fun AlarmWarningSection(activeAlarms: Map<String, String>) {
        AnimatedVisibility(visible = activeAlarms.isNotEmpty()) {
            Card(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(vertical = 16.dp),
                colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.errorContainer),
                elevation = CardDefaults.cardElevation(4.dp)
            ) {
                Row(
                    modifier = Modifier.padding(16.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Icon(
                        imageVector = Icons.Default.Warning,
                        contentDescription = "Alerta",
                        tint = MaterialTheme.colorScheme.onErrorContainer,
                        modifier = Modifier.size(40.dp)
                    )
                    Spacer(modifier = Modifier.width(16.dp))
                    Column {
                        Text(
                            text = "ALERTA DE SEGURANÇA!",
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.Bold,
                            color = MaterialTheme.colorScheme.onErrorContainer
                        )
                        activeAlarms.values.distinct().forEach { location ->
                            Text(
                                text = "- Incidente em: $location",
                                style = MaterialTheme.typography.bodyMedium,
                                color = MaterialTheme.colorScheme.onErrorContainer
                            )
                        }
                    }
                }
            }
        }
    }


    @OptIn(ExperimentalMaterial3Api::class)
    @Composable
    fun DeviceSelector(
        devices: List<Device>,
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
                        text = { Text(deviceInfo.sensor_id) },
                        onClick = {
                            onDeviceSelected(deviceInfo.sensor_id)
                            expanded = false
                        }
                    )
                }
            }
        }
    }

    @Composable
    fun DeviceReadingComponent(deviceInfo: Device) {
        val scope = rememberCoroutineScope()
        var onDemandData by remember { mutableStateOf<Device?>(null) }
        var requestStatus by remember { mutableStateOf("") }
        val apiService = RetrofitClient.instance

        LaunchedEffect(deviceInfo.sensor_id) {
            onDemandData = null
            requestStatus = ""
        }

        val displayDevice = onDemandData ?: deviceInfo

        fun sendDeviceCommand(command: String) {
            scope.launch(Dispatchers.IO) {
                requestStatus = "Enviando '$command'..."
                try {
                    val payload = CommandPayload(command)
                    val response = apiService.sendCommand(displayDevice.sensor_id, payload)
                    requestStatus = if (response.isSuccessful) {
                        response.body()?.get("message") ?: "Comando enviado com sucesso."
                    } else {
                        "Erro: ${response.code()}"
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
                Text(text = displayDevice.sensor_id, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                Spacer(Modifier.height(10.dp))

                Text(
                    text = "${displayDevice.value} ${displayDevice.unit?.let { it } ?: ""}".trim(),
                    style = MaterialTheme.typography.headlineMedium,
                    color = if (onDemandData != null) MaterialTheme.colorScheme.primary else LocalContentColor.current
                )
                Text(
                    "em ${formatTimestamp(displayDevice.timestamp)}",
                    style = MaterialTheme.typography.bodySmall
                )

                Spacer(Modifier.height(10.dp))

                Button(onClick = {
                    scope.launch(Dispatchers.IO) {
                        requestStatus = "Requisitando dados..."
                        try {
                            val response = apiService.getOnDemandData(deviceInfo.sensor_id)
                            if (response.isSuccessful) {
                                val device = response.body()
                                if (device != null) {
                                    onDemandData = device
                                    requestStatus = "Leitura atualizada"
                                } else {
                                    requestStatus = "Dispositivo não retornou dados."
                                }
                            } else {
                                requestStatus = "Timeout ou erro no gateway."
                            }
                        } catch (e: Exception) {
                            requestStatus = "Erro: ${e.message}"
                        }
                    }
                }) {
                    Text("Requisitar Leitura")
                }

                when (displayDevice.sensorType) {
                    "SEMAPHORE" -> {
                        Button(onClick = { sendDeviceCommand("vermelho") }) {
                            Text("Fechar semáforo")
                        }
                        Button(onClick = { sendDeviceCommand("verde") }) {
                            Text("Abrir semáforo")
                        }
                    }
                    "LAMP_POST" -> {
                        Row(horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                            Button(onClick = { sendDeviceCommand("on") }) { Text("ON") }
                            Button(onClick = { sendDeviceCommand("off") }) { Text("OFF") }
                        }
                    }
                    else -> {}
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
        return sdf.format(Date(timestamp * 1000))
    }
}
