[app]
title = Kia Co-Pilot
package.name = kiacopilot
package.domain = org.abhay
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
version = 1.0
requirements = python3,kivy==2.3.0,plyer,requests,spotipy
android.permissions = INTERNET, RECORD_AUDIO
android.api = 33
android.minapi = 21
android.accept_sdk_license = True
fullscreen = 0
orientation = portrait

[buildozer]
log_level = 2
warn_on_root = 0
