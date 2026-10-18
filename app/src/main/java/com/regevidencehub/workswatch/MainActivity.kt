package com.regevidencehub.workswatch

import android.content.Intent
import android.content.Context
import android.net.Uri
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.History
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.Visibility
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.launch
import java.text.DateFormat
import java.util.Date

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { WorksWatchApp(this) }
    }
}

private enum class Destination(val title: String) { HOME("Home"), WATCHES("Watches"), ACTIVITY("Activity") }

@Composable
private fun WorksWatchApp(activity: ComponentActivity) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val dark = isSystemInDarkTheme()
    val colors = if (dark) darkColorScheme(
        primary = Color(0xFF72D2C6), onPrimary = Color(0xFF003732), secondary = Color(0xFFB5CCC7),
        background = Color(0xFF101817), surface = Color(0xFF17211F), surfaceVariant = Color(0xFF263431),
        onSurface = Color(0xFFE1EAE7), onSurfaceVariant = Color(0xFFB3C4BF),
    ) else lightColorScheme(
        primary = Color(0xFF087E78), onPrimary = Color.White, secondary = Color(0xFF426A65),
        background = Color(0xFFF6F8F7), surface = Color.White, surfaceVariant = Color(0xFFE8F0EE),
        onSurface = Color(0xFF182421), onSurfaceVariant = Color(0xFF52645F),
    )
    var catalog by remember { mutableStateOf<Catalog?>(null) }
    var watch by remember { mutableStateOf<WatchCase?>(null) }
    var destination by remember { mutableStateOf(Destination.HOME) }
    var pickerOpen by remember { mutableStateOf(false) }
    var selected by remember { mutableStateOf(setOf<String>()) }
    var busy by remember { mutableStateOf(false) }
    var message by remember { mutableStateOf<String?>(null) }
    var price by remember { mutableStateOf<String?>(null) }
    var billingRevision by remember { mutableIntStateOf(0) }

    val billing = remember {
        PlayBilling(context) { purchaseToken ->
            val token = watch?.token ?: return@PlayBilling
            scope.launch {
                busy = true
                try {
                    if (MobileApi.verifyPurchase(token, purchaseToken)) {
                        CaseVault.save(context, token)
                        watch = MobileApi.status(token)
                        message = "Your watch is active for 30 days."
                    }
                } catch (e: Exception) {
                    message = e.message ?: "Purchase verification is pending. Check again shortly."
                    runCatching { watch = MobileApi.status(token) }
                } finally { busy = false }
            }
        }
    }
    billing.onUpdate = { billingRevision++; price = billing.localizedPrice; if (billing.message != null) message = billing.message }

    LaunchedEffect(Unit) {
        busy = true
        try {
            catalog = MobileApi.catalog()
            val saved = CaseVault.load(context)
            if (saved != null) {
                watch = runCatching { MobileApi.status(saved) }.getOrNull()
                if (watch == null) CaseVault.clear(context)
            }
        } catch (e: Exception) { message = e.message ?: "Can’t reach the source service right now." }
        finally { busy = false }
    }

    LaunchedEffect(catalog?.productId, watch?.token) {
        val c = catalog
        if (c != null) billing.connect(watch?.token, c.productId, c.purchaseOptionId)
    }
    DisposableEffect(Unit) { onDispose { billing.close() } }

    MaterialTheme(colorScheme = colors) {
        Scaffold(
            containerColor = colors.background,
            bottomBar = {
                NavigationBar(containerColor = colors.surface) {
                    Destination.entries.forEach { tab ->
                        NavigationBarItem(
                            selected = destination == tab && !pickerOpen,
                            onClick = { destination = tab; pickerOpen = false; message = null },
                            icon = { Icon(when (tab) {
                                Destination.HOME -> Icons.Default.Home
                                Destination.WATCHES -> Icons.Default.Visibility
                                Destination.ACTIVITY -> Icons.Default.History
                            }, contentDescription = null) },
                            label = { Text(tab.title) },
                        )
                    }
                }
            },
        ) { padding ->
            Column(Modifier.fillMaxSize().padding(padding)) {
                Row(Modifier.fillMaxWidth().padding(horizontal = 22.dp, vertical = 14.dp), verticalAlignment = Alignment.CenterVertically) {
                    Box(Modifier.size(38.dp).background(colors.primary, CircleShape), contentAlignment = Alignment.Center) {
                        Icon(Icons.Default.Visibility, null, tint = colors.onPrimary, modifier = Modifier.size(21.dp))
                    }
                    Spacer(Modifier.width(11.dp))
                    Column {
                        Text("Works Watch", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                        Text("Official source evidence", style = MaterialTheme.typography.labelMedium, color = colors.onSurfaceVariant)
                    }
                }
                if (message != null) {
                    Surface(Modifier.fillMaxWidth().padding(horizontal = 18.dp, vertical = 2.dp), color = colors.surfaceVariant, shape = RoundedCornerShape(14.dp)) {
                        Row(Modifier.padding(13.dp), verticalAlignment = Alignment.CenterVertically) {
                            Text(message.orEmpty(), Modifier.weight(1f), style = MaterialTheme.typography.bodySmall)
                            TextButton(onClick = { message = null }) { Text("Dismiss") }
                        }
                    }
                }
                when {
                    pickerOpen -> SourcePicker(catalog, selected, { selected = it }, onBack = { pickerOpen = false }, busy = busy, onCreate = {
                        val ids = selected.toList()
                        scope.launch {
                            busy = true
                            try {
                                val created = MobileApi.createCase(ids)
                                watch = created
                                CaseVault.save(context, created.token)
                                destination = Destination.WATCHES
                                pickerOpen = false
                                message = null
                            } catch (e: Exception) { message = e.message ?: "Couldn’t create a watch. Try again." }
                            finally { busy = false }
                        }
                    })
                    destination == Destination.HOME -> HomeScreen(watch, busy, onCreate = {
                        selected = catalog?.sources?.map { it.id }?.toSet().orEmpty()
                        pickerOpen = true
                    }, onView = { destination = Destination.WATCHES })
                    destination == Destination.WATCHES -> WatchesScreen(
                        watch = watch, catalog = catalog, price = price, billingRevision = billingRevision, busy = busy,
                        onCreate = {
                            selected = catalog?.sources?.map { it.id }?.toSet().orEmpty()
                            pickerOpen = true
                        },
                        onRefresh = {
                            val token = watch?.token ?: return@WatchesScreen
                            scope.launch {
                                busy = true
                                try { watch = MobileApi.status(token) }
                                catch (e: Exception) { message = e.message ?: "Couldn’t refresh source status." }
                                finally { busy = false }
                            }
                        },
                        onBuy = {
                            val token = watch?.token ?: return@WatchesScreen
                            val c = catalog ?: return@WatchesScreen
                            billing.buy(activity, token, c.productId, c.purchaseOptionId)
                        },
                    )
                    else -> ActivityScreen(watch, onOpen = { destination = Destination.WATCHES })
                }
            }
        }
    }
}

@Composable
private fun HomeScreen(watch: WatchCase?, busy: Boolean, onCreate: () -> Unit, onView: () -> Unit) {
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(start = 18.dp, end = 18.dp, top = 6.dp, bottom = 24.dp), verticalArrangement = Arrangement.spacedBy(15.dp)) {
        item {
            Column(Modifier.padding(top = 8.dp, bottom = 3.dp)) {
                Text("A clearer view of the guidance you rely on", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
                Spacer(Modifier.height(6.dp))
                Text("Check selected official sources and see when their evidence changes.", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
        item {
            if (watch != null) StatusCard(watch, onClick = onView)
            else Surface(color = MaterialTheme.colorScheme.primary, shape = RoundedCornerShape(24.dp)) {
                Column(Modifier.fillMaxWidth().padding(22.dp)) {
                    Text("Your first watch", color = Color.White.copy(alpha = .82f), style = MaterialTheme.typography.labelLarge)
                    Spacer(Modifier.height(8.dp))
                    Text("Choose the official sources you want to follow.", color = Color.White, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.SemiBold)
                    Spacer(Modifier.height(18.dp))
                    Button(onClick = onCreate, enabled = !busy, colors = ButtonDefaults.buttonColors(containerColor = Color.White, contentColor = MaterialTheme.colorScheme.primary)) {
                        Text(if (busy) "Loading…" else "Choose sources")
                    }
                }
            }
        }
        item { SectionTitle("How it works") }
        item { InfoRow("01", "Choose sources", "Start with a free, dated evidence checkpoint.") }
        item { InfoRow("02", "See source status", "Current, changed or unavailable is shown clearly.") }
        item { InfoRow("03", "Keep checking", "A one-time 30-day watch includes repeat checks.") }
        item {
            Text("England Works Watch is an independent information service. It is not a government service or legal advice.", Modifier.padding(horizontal = 3.dp, vertical = 5.dp), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

@Composable
private fun SourcePicker(catalog: Catalog?, selected: Set<String>, onSelected: (Set<String>) -> Unit, onBack: () -> Unit, busy: Boolean, onCreate: () -> Unit) {
    Column(Modifier.fillMaxSize()) {
        Row(Modifier.padding(horizontal = 16.dp, vertical = 5.dp), verticalAlignment = Alignment.CenterVertically) {
            IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "Back") }
            Text("New watch", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
        }
        LazyColumn(Modifier.weight(1f), contentPadding = PaddingValues(horizontal = 20.dp, vertical = 10.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            item {
                Text("Choose your sources", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
                Spacer(Modifier.height(7.dp))
                Text(catalog?.question ?: "Which official sources would you like to watch?", color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            items(catalog?.sources.orEmpty(), key = { it.id }) { source ->
                Surface(
                    modifier = Modifier.fillMaxWidth().clickable { onSelected(if (source.id in selected) selected - source.id else selected + source.id) },
                    shape = RoundedCornerShape(18.dp), color = MaterialTheme.colorScheme.surface,
                    border = BorderStroke(1.dp, if (source.id in selected) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.outlineVariant),
                ) {
                    Row(Modifier.padding(15.dp), verticalAlignment = Alignment.CenterVertically) {
                        Checkbox(source.id in selected, onCheckedChange = { onSelected(if (it) selected + source.id else selected - source.id) })
                        Spacer(Modifier.width(6.dp))
                        Column(Modifier.weight(1f)) {
                            Text(source.title, fontWeight = FontWeight.SemiBold, maxLines = 2, overflow = TextOverflow.Ellipsis)
                            Spacer(Modifier.height(3.dp))
                            Text(if (source.current) "Source available" else "Source unavailable", style = MaterialTheme.typography.labelSmall, color = if (source.current) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.error)
                        }
                    }
                }
            }
            item { Text("The service checks changes in official source evidence. It does not decide what a change means for a specific case.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
        }
        Surface(color = MaterialTheme.colorScheme.surface) {
            Button(onClick = onCreate, enabled = selected.isNotEmpty() && !busy, modifier = Modifier.fillMaxWidth().padding(horizontal = 20.dp, vertical = 14.dp).height(52.dp), shape = RoundedCornerShape(16.dp)) {
                Text(if (busy) "Creating checkpoint…" else "Create free checkpoint")
            }
        }
    }
}

@Composable
private fun WatchesScreen(
    watch: WatchCase?, catalog: Catalog?, price: String?, billingRevision: Int, busy: Boolean,
    onCreate: () -> Unit, onRefresh: () -> Unit, onBuy: () -> Unit,
) {
    val context = LocalContext.current
    @Suppress("UNUSED_EXPRESSION") val revision = billingRevision
    if (watch == null) {
        EmptyScreen("No watches yet", "Choose official sources to create a free checkpoint.", "Create a watch", onCreate)
        return
    }
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(horizontal = 18.dp, vertical = 8.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        item { StatusCard(watch, onClick = onRefresh) }
        item {
            Row(verticalAlignment = Alignment.CenterVertically) {
                SectionTitle("Selected sources", Modifier.weight(1f))
                TextButton(onClick = onRefresh, enabled = !busy) { Text(if (busy) "Checking…" else "Check now") }
            }
        }
        items(watch.report.sources, key = { it.first }) { (id, status) ->
            val source = catalog?.sources?.firstOrNull { it.id == id }
            Surface(shape = RoundedCornerShape(16.dp), color = MaterialTheme.colorScheme.surface) {
                Column(Modifier.fillMaxWidth().padding(16.dp)) {
                    Text(source?.title ?: "Selected official source", fontWeight = FontWeight.SemiBold)
                    Spacer(Modifier.height(5.dp))
                    StatusChip(statusLabel(status), status == "UNCHANGED")
                    if (source != null) {
                        Spacer(Modifier.height(9.dp))
                        TextButton(onClick = { openExternal(context, source.url) }, contentPadding = PaddingValues(0.dp)) { Text("Open official source") }
                    }
                }
            }
        }
        if (watch.active) {
            item {
                Surface(color = MaterialTheme.colorScheme.primaryContainer, shape = RoundedCornerShape(18.dp)) {
                    Column(Modifier.fillMaxWidth().padding(17.dp)) {
                        Text("30-day watch active", fontWeight = FontWeight.Bold)
                        Text(watch.expiresAt?.let { "Access through ${DateFormat.getDateInstance(DateFormat.MEDIUM).format(Date(it * 1000))}" } ?: "Repeat checks are available for 30 days.", style = MaterialTheme.typography.bodySmall)
                        if (watch.consumePending) Text("Google Play is finishing the purchase update.", style = MaterialTheme.typography.bodySmall)
                    }
                }
            }
        } else if (watch.purchaseAvailable) {
            item {
                Surface(shape = RoundedCornerShape(22.dp), color = MaterialTheme.colorScheme.surface, border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant)) {
                    Column(Modifier.fillMaxWidth().padding(19.dp)) {
                        Text("Keep this evidence in view", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                        Spacer(Modifier.height(7.dp))
                        Text("A one-time payment starts 30 days of repeat checks for these sources.", color = MaterialTheme.colorScheme.onSurfaceVariant)
                        Spacer(Modifier.height(5.dp))
                        Text("No subscription. No auto-renewal.", style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.Medium)
                        Spacer(Modifier.height(15.dp))
                        Button(onClick = onBuy, enabled = price != null && !busy, modifier = Modifier.fillMaxWidth().height(50.dp), shape = RoundedCornerShape(15.dp)) {
                            Text(if (price != null) "Continue with Google Play · $price" else "Loading Google Play price…")
                        }
                        Spacer(Modifier.height(6.dp))
                        Text("Price shown by Google Play for your account and region.", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
            }
        } else {
            item { InfoRow("", "Purchase not available", "Official source evidence needs review before this watch can be started.") }
        }
        item { Text("A changed or unavailable source calls for human review. This watch does not provide legal conclusions or alerts outside the app.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
    }
}

@Composable
private fun ActivityScreen(watch: WatchCase?, onOpen: () -> Unit) {
    if (watch == null) {
        EmptyScreen("Your activity", "Your checkpoint and source checks will appear here.", null, {})
        return
    }
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(18.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        item { Text("Recent activity", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold) }
        item {
            Surface(Modifier.fillMaxWidth().clickable(onClick = onOpen), shape = RoundedCornerShape(18.dp), color = MaterialTheme.colorScheme.surface) {
                Column(Modifier.padding(18.dp)) {
                    Text(if (watch.active) "30-day watch" else "Evidence checkpoint", fontWeight = FontWeight.SemiBold)
                    Spacer(Modifier.height(7.dp))
                    StatusChip(watch.report.label, watch.report.status == "UNCHANGED")
                    Spacer(Modifier.height(8.dp))
                    Text(watch.report.checkedAt.ifBlank { watch.createdAt }.ifBlank { "Checked just now" }, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Text("View source details", modifier = Modifier.padding(top = 7.dp), color = MaterialTheme.colorScheme.primary, style = MaterialTheme.typography.labelLarge)
                }
            }
        }
    }
}

@Composable
private fun StatusCard(watch: WatchCase, onClick: () -> Unit) {
    val good = watch.report.status == "UNCHANGED"
    Surface(Modifier.fillMaxWidth().clickable(onClick = onClick), color = MaterialTheme.colorScheme.surface, shape = RoundedCornerShape(22.dp), border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant)) {
        Column(Modifier.padding(19.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(if (good) Icons.Default.CheckCircle else Icons.Default.Visibility, null, tint = if (good) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.tertiary)
                Spacer(Modifier.width(9.dp))
                Text(if (watch.active) "Your source watch" else "Your checkpoint", color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.labelLarge)
            }
            Spacer(Modifier.height(12.dp))
            Text(watch.report.label, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
            Spacer(Modifier.height(5.dp))
            Text(if (good) "The selected source versions match your checkpoint." else "Review the current official evidence before relying on earlier information.", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Spacer(Modifier.height(12.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                StatusChip("${watch.report.sources.size} sources", true)
                if (watch.active) StatusChip("30 days", true)
            }
        }
    }
}

@Composable
private fun StatusChip(text: String, positive: Boolean) {
    Surface(color = if (positive) MaterialTheme.colorScheme.primaryContainer else MaterialTheme.colorScheme.errorContainer, shape = RoundedCornerShape(40.dp)) {
        Text(text, Modifier.padding(horizontal = 11.dp, vertical = 6.dp), style = MaterialTheme.typography.labelMedium, color = if (positive) MaterialTheme.colorScheme.onPrimaryContainer else MaterialTheme.colorScheme.onErrorContainer)
    }
}

@Composable
private fun InfoRow(number: String, title: String, body: String) {
    Surface(color = MaterialTheme.colorScheme.surface, shape = RoundedCornerShape(16.dp)) {
        Row(Modifier.fillMaxWidth().padding(15.dp), verticalAlignment = Alignment.Top) {
            if (number.isNotEmpty()) Text(number, color = MaterialTheme.colorScheme.primary, fontWeight = FontWeight.Bold, modifier = Modifier.width(36.dp))
            Column {
                Text(title, fontWeight = FontWeight.SemiBold)
                Spacer(Modifier.height(3.dp))
                Text(body, color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodySmall)
            }
        }
    }
}

@Composable
private fun EmptyScreen(title: String, body: String, action: String?, onAction: () -> Unit) {
    Column(Modifier.fillMaxSize().padding(26.dp), verticalArrangement = Arrangement.Center, horizontalAlignment = Alignment.CenterHorizontally) {
        Icon(Icons.Default.Visibility, null, tint = MaterialTheme.colorScheme.primary, modifier = Modifier.size(42.dp))
        Spacer(Modifier.height(15.dp))
        Text(title, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
        Spacer(Modifier.height(6.dp))
        Text(body, color = MaterialTheme.colorScheme.onSurfaceVariant)
        if (action != null) { Spacer(Modifier.height(18.dp)); Button(onClick = onAction) { Text(action) } }
    }
}

@Composable
private fun SectionTitle(text: String, modifier: Modifier = Modifier) = Text(text, modifier, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)

private fun statusLabel(status: String) = boundedStatusLabel(status)

private fun openExternal(context: Context, url: String) { runCatching { context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url))) } }
