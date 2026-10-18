package com.regevidencehub.workswatch

import org.junit.Assert.assertEquals
import org.junit.Test

class BoundedStatusLabelTest {
    @Test fun unchangedEvidenceUsesBoundedCopy() = assertEquals("No verified change", boundedStatusLabel("UNCHANGED"))
    @Test fun changedEvidenceRequestsReviewWithoutConclusion() = assertEquals("Change detected", boundedStatusLabel("CHANGED"))
    @Test fun unknownAndUnavailableStatesFailClosed() = assertEquals("Review needed", boundedStatusLabel("UNAVAILABLE"))
}
