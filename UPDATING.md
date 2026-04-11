### To release a new version of the addon, follow these steps:

1. Update the version number in the plugin.video.tidb/addon.xml file.
2. Copy the plugin.video.tidb/addon.xml addon manifest to the addons.xml file.
3. Create a new release on GitHub with the updated version number and a description of the changes.
4. Zip and upload both the plugin.video.tidb and repository.tidb.repo and upload them to the release.

This addon uses **GitHub Releases** for distribution. When a new version is released, the addons.xml file contains the latest version url (e.g., v1.2.2/plugin.video.tidb.zip), which is appended to the addons.xml zip directory (https://github.com/TheIntroDB/kodi-addon/releases/download/)

