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
    var localizedPrice: String? = null
        private set
    var message: String? = null
        private set
    var onUpdate: (() -> Unit)? = null

    private val listener = PurchasesUpdatedListener { result, purchases ->
        if (result.responseCode == BillingClient.BillingResponseCode.OK && purchases != null) {
            purchases.filter { it.purchaseState == Purchase.PurchaseState.PURCHASED }
                .forEach { purchase -> purchaseToken(purchase.purchaseToken) }
        } else if (result.responseCode != BillingClient.BillingResponseCode.USER_CANCELED) {
            message = "Google Play could not complete the purchase. Try again."
            onUpdate?.invoke()
        }
    }

    private val client = BillingClient.newBuilder(appContext)
        .setListener(listener)
        .enablePendingPurchases(PendingPurchasesParams.newBuilder().enableOneTimeProducts().build())
        .build()

    fun connect(caseToken: String?, productId: String, optionId: String) {
        activeCaseToken = caseToken
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
                        message = "Google Play is not available right now."
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
            if (localizedPrice == null) message = "This one-time watch is not available in Google Play yet."
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
            message = "Google Play could not start the purchase. Try again."
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

abstract class BillingClientStateListenerAdapter : com.android.billingclient.api.BillingClientStateListener {
    final override fun onBillingSetupFinished(result: BillingResult) = connected(result)
    final override fun onBillingServiceDisconnected() = disconnected()
    abstract fun connected(result: BillingResult)
    open fun disconnected() = Unit
}
