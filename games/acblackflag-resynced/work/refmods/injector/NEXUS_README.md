# Encryptedstudios Forge Injector v1.0

A standalone FORGE v50 resource injector for **Assassin's Creed IV: Black Flag Resynced**.

## Features

- Searchable external catalogue with 729 named 64-bit Resource IDs
- Add newly discovered IDs to `AC4_Resource_IDs.txt` and press **Reload IDs**
- Inspect FORGE entries and BMS block/chunk information
- Extract complete stored entries
- Extract decoded resources from raw or Oodle-compressed BMS chunks
- Correct compression-field routing instead of assuming LZO
- Stored-chunk checksum and decoded-size verification
- Inject game-ready textures, meshes, materials, settings, and other resources
- Larger and smaller decoded replacements supported through BMS rebuilding
- Resource header + payload mode
- Complete stored-entry mode
- Dry-run planning
- Append-and-repoint injection without rebuilding the complete FORGE
- Post-write verification, backup records, and one-click revert
- Stable custom dark controls with the Windows drop-down/theme glitches removed

## What is BMS?

BMS is the chunk container wrapped around many FORGE resources. It records the number of chunks, their decoded and stored sizes, the compression field, and a checksum for each stored chunk. The actual texture, mesh, material, or settings resource is inside those chunks.

Supported compressed Black Flag Resynced entries use compression field 8 and Oodle. The injector uses the game's own `oo2core` DLL to decode them automatically.

## Installation

1. Extract the entire ZIP into its own folder.
2. Keep all supplied files beside the EXE.
3. Run `Encryptedstudios Forge Injector.exe`.

## Basic use

1. Close the game and Ubisoft Connect.
2. Select the target FORGE.
3. Search or paste a 64-bit Resource ID.
4. Press **Inspect**.
5. Select the correct BMS block, commonly block 1.
6. Press **Extract Entry** and **Extract Decoded**.
7. Edit or compile the asset into the correct game-ready resource format.
8. Click **Injection Mode** to select the required mode.
9. Press **Dry Run**.
10. Press **Inject + Verify**.
11. Use **Revert Original** when required.

## Editable Resource ID list

```text
0x000002317C9DE7F3<TAB>Death Vessel Sails<TAB>Ship Sails
```

Users can add newly discovered IDs or rename existing entries, save the file, and press **Reload IDs** without rebuilding the application.

## Important

The injector installs game-ready resources. It does not automatically convert PNG/JPG into the game's texture format or OBJ/FBX/GLTF into a compiled mesh.

See `RESOURCE_INJECTION_GUIDE.txt` for the complete workflow.

Created by **Encryptedstudios**.
