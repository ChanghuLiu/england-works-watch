package com.regevidencehub.workswatch

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

data class GuidanceSource(val id: String, val title: String, val url: String, val current: Boolean)
data class WatchReport(
    val status: String,
    val label: String,
    val checkedAt: String,
    val sourceGate: Boolean,
    val sources: List<Pair<String, String>>,
)
data class WatchCase(
    val token: String,
    val createdAt: String,
    val report: WatchReport,
    val active: Boolean,
    val expiresAt: Long?,
    val purchaseAvailable: Boolean,
    val consumePending: Boolean = false,
)
data class Catalog(
    val question: String,
    val sources: List<GuidanceSource>,
    val packageName: String,
    val productId: String,
    val purchaseOptionId: String,
    val serviceDays: Int,
)

object MobileApi {
    private suspend fun request(path: String, body: JSONObject? = null): JSONObject = withContext(Dispatchers.IO) {
        val connection = (URL(BuildConfig.API_BASE_URL + path).openConnection() as HttpURLConnection).apply {
            connectTimeout = 12_000
            readTimeout = 18_000
            requestMethod = if (body == null) "GET" else "POST"
            setRequestProperty("Accept", "application/json")
            if (body != null) {
                doOutput = true
                setRequestProperty("Content-Type", "application/json; charset=utf-8")
                outputStream.use { it.write(body.toString().toByteArray(Charsets.UTF_8)) }
            }
        }
        try {
            val stream = if (connection.responseCode in 200..299) connection.inputStream else connection.errorStream
            val text = stream?.bufferedReader()?.use { it.readText() }.orEmpty()
            decodeMobileApiResponse(text, connection.responseCode)
        } finally { connection.disconnect() }
    }

    suspend fun catalog(): Catalog {
        val json = request("/api/mobile/v1/catalog")
        val rows = json.optJSONArray("sources") ?: JSONArray()
        val sources = (0 until rows.length()).mapNotNull { i ->
            rows.optJSONObject(i)?.let { row ->
                GuidanceSource(row.optString("source_id"), row.optString("title"), row.optString("url"), row.optString("status") == "CURRENT")
            }
        }
        return Catalog(
            json.optString("question", "Which official sources would you like to watch?"), sources,
            json.optString("package_name"), json.optString("product_id"), json.optString("purchase_option_id"),
            json.optInt("service_days", 30),
        )
    }

    suspend fun createCase(sourceIds: List<String>): WatchCase {
        val json = request("/api/mobile/v1/cases", JSONObject().put("source_ids", JSONArray(sourceIds)))
        return WatchCase(
            json.getString("case_token"), json.optString("created_at"), parseReport(json.optJSONObject("report")),
            false, null, json.optBoolean("purchase_available"),
        )
    }

    suspend fun status(caseToken: String): WatchCase {
        val json = request("/api/mobile/v1/status", JSONObject().put("case_token", caseToken))
        return WatchCase(
            caseToken, "", parseReport(json.optJSONObject("report")), json.optString("status") == "ACTIVE",
            json.optLong("access_expires_at").takeIf { it > 0 }, json.optBoolean("purchase_available"),
            json.optBoolean("consume_pending"),
        )
    }

    suspend fun verifyPurchase(caseToken: String, purchaseToken: String): Boolean {
        val json = request("/api/mobile/v1/purchases/verify", JSONObject()
            .put("case_token", caseToken).put("purchase_token", purchaseToken))
        return json.optString("status") == "ACTIVE"
    }

    private fun parseReport(json: JSONObject?): WatchReport {
        val report = json ?: JSONObject()
        val rows = report.optJSONArray("sources") ?: JSONArray()
        val sources = (0 until rows.length()).mapNotNull { i ->
            rows.optJSONObject(i)?.let { row -> row.optString("source_id") to row.optString("status", "REVIEW_REQUIRED") }
        }
        val status = report.optString("status", "REVIEW_REQUIRED")
        val label = report.optString("status_label").ifBlank { boundedStatusLabel(status) }
        return WatchReport(status, label, report.optString("checked_at"), report.optBoolean("source_gate"), sources)
    }

}

internal fun decodeMobileApiResponse(text: String, statusCode: Int): JSONObject {
    val result = if (text.isBlank()) JSONObject() else try {
        JSONObject(text)
    } catch (_: org.json.JSONException) {
        if (statusCode in 200..299) {
            throw IllegalStateException("The mobile service returned an invalid response.")
        }
        JSONObject()
    }
    if (statusCode !in 200..299) {
        val message = result.optString("message").ifBlank { result.optString("status") }
            .ifBlank { "Service unavailable. Try again shortly." }
        throw IllegalStateException(message)
    }
    return result
}

internal fun boundedStatusLabel(status: String): String = when (status) {
    "UNCHANGED" -> "No verified change"
    "CHANGED" -> "Change detected"
    else -> "Review needed"
}
