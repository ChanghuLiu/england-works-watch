package com.regevidencehub.workswatch

import android.app.Activity
import android.content.Context
import com.android.billingclient.api.BillingClient
import com.android.billingclient.api.BillingFlowParams
import com.android.billingclient.api.BillingResult
import com.android.billingclient.api.PendingPurchasesParams
import com.android.billingclient.api.ProductDetails
import com.android.billingclient.api.Purchase
import com.android.billingclient.api.PurchasesUpdatedListener
import com.android.billingclient.api.QueryProductDetailsParams
import com.android.billingclient.api.QueryPurchasesParams

class PlayBilling(context: Context, private val purchaseToken: (String) -> Unit) {
    private val appContext = context.applicationContext
    private var detail: ProductDetails? = null
    private var offer: ProductDetails.OneTimePurchaseOfferDetails? = null
    private var activeCaseToken: String? = null
    private var activeProductId: String = ""
    private var activeOptionId: String = ""
    var localizedPrice: String? = null
        private set
    var message: String? = null
        private set
    var onUpdate: (() -> Unit)? = null

    private val listener = PurchasesUpdatedListener { result, purchases ->
        val diagnostic = billingLookupDiagnostic(
            result = result,
            productId = activeProductId,
            optionId = activeOptionId,
            productFound = detail != null,
            offerFound = offer != null,
        )
        if (result.responseCode == BillingClient.BillingResponseCode.OK && purchases != null) {
            purchases.filter { it.purchaseState == Purchase.PurchaseState.PURCHASED }
                .forEach { purchase -> purchaseToken(purchase.purchaseToken) }
        } else if (result.responseCode != BillingClient.BillingResponseCode.USER_CANCELED) {
            message = "Google Play could not complete this one-time offer. Free checkpoints remain available. $diagnostic"
            onUpdate?.invoke()
        }
    }

    private val client = BillingClient.newBuilder(appContext)
        .setListener(listener)
        .enablePendingPurchases(PendingPurchasesParams.newBuilder().enableOneTimeProducts().build())
        .build()

    fun connect(caseToken: String?, productId: String, optionId: String) {
        activeCaseToken = caseToken
        activeProductId = productId
        activeOptionId = optionId
        if (client.isReady) {
            queryPrice(productId, optionId)
            restorePurchases()
        } else {
            client.startConnection(object : BillingClientStateListenerAdapter() {
                override fun connected(result: BillingResult) {
                    if (result.responseCode == BillingClient.BillingResponseCode.OK) {
                        queryPrice(productId, optionId)
                        restorePurchases()
                    } else {
                        message = "Google Play setup did not finish. Free checkpoints remain available. Product $productId / option $optionId; Billing response ${result.responseCode}."
                        onUpdate?.invoke()
                    }
                }
            })
        }
    }

    private fun queryPrice(productId: String, optionId: String) {
        val product = QueryProductDetailsParams.Product.newBuilder()
            .setProductId(productId).setProductType(BillingClient.ProductType.INAPP).build()
        val params = QueryProductDetailsParams.newBuilder().setProductList(listOf(product)).build()
        client.queryProductDetailsAsync(params) { result, response ->
            val selected = if (result.responseCode == BillingClient.BillingResponseCode.OK) {
                response.productDetailsList.firstOrNull { it.productId == productId }
            } else null
            val selectedOffer = selected?.oneTimePurchaseOfferDetailsList?.firstOrNull {
                it.purchaseOptionId == optionId && !it.offerToken.isNullOrBlank()
            }
            detail = selected
            offer = selectedOffer
            localizedPrice = selectedOffer?.formattedPrice
            message = billingLookupDiagnostic(
                result = result,
                productId = productId,
                optionId = optionId,
                productFound = selected != null,
                offerFound = selectedOffer != null,
            )
            onUpdate?.invoke()
        }
    }

    fun buy(activity: Activity, caseToken: String, productId: String, optionId: String) {
        activeCaseToken = caseToken
        val chosen = detail
        val chosenOffer = offer
        if (chosen == null || chosenOffer == null) {
            queryPrice(productId, optionId)
            message = "Loading the Google Play price. Try again in a moment."
            onUpdate?.invoke()
            return
        }
        val offerToken = chosenOffer.offerToken ?: return
        val productParams = BillingFlowParams.ProductDetailsParams.newBuilder()
            .setProductDetails(chosen)
            .setOfferToken(offerToken)
            .build()
        val flow = BillingFlowParams.newBuilder().setProductDetailsParamsList(listOf(productParams)).build()
        val result = client.launchBillingFlow(activity, flow)
        if (result.responseCode != BillingClient.BillingResponseCode.OK) {
            message = "Google Play could not open this offer. Your free checkpoint remains available. Product $productId / option $optionId; Billing response ${result.responseCode}."
            onUpdate?.invoke()
        }
    }

    private fun restorePurchases() {
        if (activeCaseToken == null) return
        val params = QueryPurchasesParams.newBuilder().setProductType(BillingClient.ProductType.INAPP).build()
        client.queryPurchasesAsync(params) { result, purchases ->
            if (result.responseCode == BillingClient.BillingResponseCode.OK) {
                purchases.filter { it.purchaseState == Purchase.PurchaseState.PURCHASED }
                    .forEach { purchaseToken(it.purchaseToken) }
            }
        }
    }

    fun close() { if (client.isReady) client.endConnection() }
}

internal fun billingLookupDiagnostic(
    result: BillingResult,
    productId: String,
    optionId: String,
    productFound: Boolean,
    offerFound: Boolean,
): String? {
    // Billing debug messages are opaque provider text and must not reach the UI.
    val responseCode = result.responseCode
    if (responseCode == BillingClient.BillingResponseCode.OK && productFound && offerFound) return null
    val reason = when {
        responseCode != BillingClient.BillingResponseCode.OK -> "Google Play could not load the offer."
        !productFound -> "Google Play did not return the configured product."
        else -> "The product was returned without the configured one-time purchase option."
    }
    return "$reason Product $productId / option $optionId; Billing response $responseCode. The free checkpoint remains available."
}

abstract class BillingClientStateListenerAdapter : com.android.billingclient.api.BillingClientStateListener {
    final override fun onBillingSetupFinished(result: BillingResult) = connected(result)
    final override fun onBillingServiceDisconnected() = disconnected()
    abstract fun connected(result: BillingResult)
    open fun disconnected() = Unit
}
