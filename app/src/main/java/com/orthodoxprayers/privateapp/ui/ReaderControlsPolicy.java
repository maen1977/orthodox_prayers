package com.orthodoxprayers.privateapp.ui;

/** Pure scroll-state policy used by ReaderScreen and covered by unit tests. */
public final class ReaderControlsPolicy {
    public enum Action { NONE, COLLAPSE, EXPAND }

    private final int collapseDistancePx;
    private final int expandDistancePx;
    private boolean expanded;
    private int accumulator;

    public ReaderControlsPolicy(int collapseDistancePx, int expandDistancePx, boolean expanded) {
        this.collapseDistancePx = Math.max(1, collapseDistancePx);
        this.expandDistancePx = Math.max(1, expandDistancePx);
        this.expanded = expanded;
    }

    public Action onScroll(int dy, boolean userDragging, boolean canScrollUp) {
        if (!userDragging || dy == 0) return Action.NONE;

        if (dy > 0) {
            if (accumulator < 0) accumulator = 0;
            accumulator += dy;
            if (expanded && canScrollUp && accumulator >= collapseDistancePx) {
                expanded = false;
                accumulator = 0;
                return Action.COLLAPSE;
            }
            return Action.NONE;
        }

        if (accumulator > 0) accumulator = 0;
        accumulator += dy;
        if (!expanded && accumulator <= -expandDistancePx) {
            expanded = true;
            accumulator = 0;
            return Action.EXPAND;
        }
        return Action.NONE;
    }

    public void setExpanded(boolean expanded) {
        this.expanded = expanded;
        accumulator = 0;
    }

    public void resetGesture() { accumulator = 0; }
    public boolean isExpanded() { return expanded; }
}
