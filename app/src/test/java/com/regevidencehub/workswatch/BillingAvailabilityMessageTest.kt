package com.regevidencehub.workswatch

import com.android.billingclient.api.BillingClient
import com.android.billingclient.api.BillingResult
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class BillingAvailabilityMessageTest {
    @Test fun unavailableProductMessageIncludesExactResponseAndConfiguredIds() {
        val message = billingLookupDiagnostic(
            billingResult(BillingClient.BillingResponseCode.ITEM_UNAVAILABLE, "not available to this user"),
            "works_watch_30d",
            "one-watch",
            productFound = false,
            offerFound = false,
        )!!
        assertTrue(message.contains("Billing response ${BillingClient.BillingResponseCode.ITEM_UNAVAILABLE}"))
        assertTrue(message.contains("works_watch_30d / option one-watch"))
        assertTrue(message.contains("free checkpoint remains available"))
    }

    @Test fun missingConfiguredOptionIsDistinctFromMissingProduct() {
        val message = billingLookupDiagnostic(billingResult(BillingClient.BillingResponseCode.OK), "works_watch_30d", "one-watch", true, false)!!
        assertTrue(message.contains("without the configured one-time purchase option"))
    }

    @Test fun availableOfferHasNoWarning() {
        assertNull(billingLookupDiagnostic(billingResult(BillingClient.BillingResponseCode.OK), "works_watch_30d", "one-watch", true, true))
    }

    @Test fun providerDebugTextIsNotIncludedInAvailabilityMessage() {
        val privateDiagnostic = "account=example@example.invalid; purchaseToken=synthetic-private-token"
        val message = billingLookupDiagnostic(
            billingResult(BillingClient.BillingResponseCode.ERROR, privateDiagnostic),
            "works_watch_30d", "one-watch", productFound = false, offerFound = false,
        )!!
        assertFalse(message.contains("example@example.invalid"))
        assertFalse(message.contains("synthetic-private-token"))
        assertTrue(message.contains("Billing response ${BillingClient.BillingResponseCode.ERROR}"))
    }

    private fun billingResult(code: Int, debugMessage: String = ""): BillingResult =
        BillingResult.newBuilder().setResponseCode(code).setDebugMessage(debugMessage).build()
}
