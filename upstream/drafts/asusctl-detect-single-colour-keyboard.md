# Draft issue: detect single-colour (white) keyboards

**Repo:** OpenGamingCollective/asusctl · **Type:** feature

## Title

aura: detect single-colour keyboards from the keyboard's capability report

## Body

Some SKUs of a model ship a white-only backlight while others are RGB, under the same board name. The Zephyrus G16 GU605MI is one: the -QR081W is sold as "Backlit Chiclet Keyboard Single Light", other GU605MI SKUs as 1-zone RGB. asusd offers colour and rainbow modes on both, so on a white keyboard every colour shows as white and rainbow modes pulse white. Users (and UI front-ends) can't tell whether something is broken.

The keyboard can say which it is. G-Helper probes it (`Aura.DetectBacklightType`, `AsusHid.AuraProbe`): on report `0x5d`, send `b9`, then `"ASUS Tech.Inc."`, then the query `05 20 31 00 20`, and read the `0x5d` feature report back. On this GU605MI-QR081W (USB `0b05:19b6`):

```
5d 05 20 31 00 20 01 00 00 00 23 04 01 00 56 03 0f 04 00 00
type=0x00 year=0x23 layout=0x01 feat1=0x00 feat2=0x56 family=0x04 (Zephyrus)
```

`feat2` bit `0x08` (G-Helper's `FEAT2_RGB_WHEEL`, what makes Armoury Crate show a colour wheel) is clear, and bit `0x10` (`FEAT2_ONE_ZONE_RED_EFFECT`) is set.

Note that G-Helper's own rule, `typeByte != 0x00 && (feat2 & 0x10)`, would **not** flag this keyboard, because it reports type `0x00`. The RGB-wheel bit looks like the more reliable signal for 2023-and-later keyboards (`year >= 0x23`), or the two combined.

**Proposal:** probe once at startup; when the keyboard has no RGB wheel, expose that over D-Bus (e.g. `SupportsColour: false` on `xyz.ljones.Aura`) and leave colour out of `SupportedBasicModes` handling in clients: G-Helper offers only Static, Breathe and Strobe on white keyboards. Front-ends like rog-control-center could then hide the colour picker.

I can test patches on this unit.
