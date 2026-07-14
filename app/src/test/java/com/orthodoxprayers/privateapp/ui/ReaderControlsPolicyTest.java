package com.orthodoxprayers.privateapp.ui;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

public final class ReaderControlsPolicyTest {
    @Test
    public void collapsesOnlyAfterEnoughUserScroll() {
        ReaderControlsPolicy policy = new ReaderControlsPolicy(60, 80, true);
        assertEquals(ReaderControlsPolicy.Action.NONE, policy.onScroll(30, true, true));
        assertEquals(ReaderControlsPolicy.Action.NONE, policy.onScroll(29, true, true));
        assertEquals(ReaderControlsPolicy.Action.COLLAPSE, policy.onScroll(1, true, true));
        assertFalse(policy.isExpanded());
    }

    @Test
    public void doesNotCollapseAtTopOrForProgrammaticScroll() {
        ReaderControlsPolicy policy = new ReaderControlsPolicy(60, 80, true);
        assertEquals(ReaderControlsPolicy.Action.NONE, policy.onScroll(90, true, false));
        assertTrue(policy.isExpanded());
        assertEquals(ReaderControlsPolicy.Action.NONE, policy.onScroll(90, false, true));
        assertTrue(policy.isExpanded());
    }

    @Test
    public void expandsOnlyAfterDeliberateReverseScroll() {
        ReaderControlsPolicy policy = new ReaderControlsPolicy(60, 80, false);
        assertEquals(ReaderControlsPolicy.Action.NONE, policy.onScroll(-40, true, true));
        assertEquals(ReaderControlsPolicy.Action.EXPAND, policy.onScroll(-40, true, true));
        assertTrue(policy.isExpanded());
    }

    @Test
    public void directionChangeResetsAccumulation() {
        ReaderControlsPolicy policy = new ReaderControlsPolicy(60, 80, true);
        policy.onScroll(40, true, true);
        policy.onScroll(-10, true, true);
        assertEquals(ReaderControlsPolicy.Action.NONE, policy.onScroll(30, true, true));
        assertTrue(policy.isExpanded());
    }
}
