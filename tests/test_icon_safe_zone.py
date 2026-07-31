from pathlib import Path
import unittest
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
class IconSafeZoneTests(unittest.TestCase):
 def test_foreground_is_108_canvas_and_art_fits_66_safe_zone(self):
  p=ROOT/"app/src/main/res/drawable-nodpi/church_prayers_cross_foreground.png"
  im=Image.open(p).convert("RGBA"); self.assertEqual((108,108),im.size)
  box=im.getchannel("A").getbbox(); self.assertIsNotNone(box); self.assertLessEqual(box[2]-box[0],66); self.assertLessEqual(box[3]-box[1],66)
 def test_adaptive_layer_uses_safe_foreground(self):
  text=(ROOT/"app/src/main/res/drawable/ic_launcher_foreground.xml").read_text(encoding="utf-8")
  self.assertIn("@drawable/church_prayers_cross_foreground",text); self.assertNotIn("20dp",text)
if __name__=="__main__": unittest.main()
