[app]
title = WormRhombus
package.name = worm
package.domain = org.example
source.dir = .
source.include_exts = py
version = 0.1

requirements = python3,kivy,plyer
orientation = landscape

[buildozer]
log_level = 2

[android]
android.api = 33
android.minapi = 23
android.ndk = 25b
android.permissions = VIBRATE
