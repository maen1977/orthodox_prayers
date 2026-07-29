# Small Compline category compatibility fix — 5.0.20

The 5.0.19 Android runtime loaded native language libraries where `small_compline` was categorized as `liturgy`, while signed rolling-week overlays correctly used the reviewed source category `daily`. Runtime inheritance validation therefore rejected the whole signed package with `invalid_service_base_category_mismatch:small_compline`.

The native-pack builder now treats service category as structural source metadata. Language overrides may replace native text but cannot change category. Native Arabic, English, and Greek packs were rebuilt; `small_compline` is now `daily` in all three. Existing signed rolling-week data can be accepted by 5.0.20 without republishing it.
