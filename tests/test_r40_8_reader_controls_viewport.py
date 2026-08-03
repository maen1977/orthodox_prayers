from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_expanded_reader_controls_are_scrollable_and_height_capped() -> None:
    reader = read("app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/ReaderScreen.java")
    assert "private MaxHeightScrollView controlsViewport;" in reader
    assert "Math.round(displayHeight * 0.38f)" in reader
    assert "Math.min(\n                ui.dp(340)" in reader
    assert "controlsViewport.addView(controlsPanel" in reader
    assert "controlsViewport.setVerticalScrollBarEnabled(true)" in reader
    assert "controlsViewport.setVisibility(controlsExpanded ? View.VISIBLE : View.GONE)" in reader
    assert "recycler.setMinimumHeight(ui.dp(180))" in reader
    assert "protected void onMeasure" in reader
    assert "MeasureSpec.getSize(heightMeasureSpec)" in reader
    assert "MeasureSpec.AT_MOST" in reader


def test_reader_smoke_test_rejects_a_collapsed_viewport() -> None:
    smoke = read("app/src/androidTest/java/com/orthodoxprayers/privateapp/ReaderSmokeTest.java")
    assert "MINIMUM_READER_VIEWPORT_DP = 120" in smoke
    assert "minimumHeightPx" in smoke
    assert "height >= minimumHeightPx" in smoke
    assert "Reader viewport is too short while controls are visible" in smoke
