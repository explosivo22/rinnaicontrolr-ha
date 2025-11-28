# Migration Guide: Upgrading to Rinnai Control-R v2.0.0

## ⚠️ Breaking Change: Directory Rename

Version 2.0.0 includes a **breaking change** that requires manual intervention when upgrading. The integration directory has been renamed from `rinnaicontrolr-ha` to `rinnai` to follow Home Assistant best practices (matching the integration domain).

| Version | Directory Name |
|---------|----------------|
| v1.5.x / v2.1.x (Old) | `custom_components/rinnaicontrolr-ha/` |
| v2.0.0 (New) | `custom_components/rinnai/` |

> **Note:** Your configuration data and entity IDs will be preserved since the integration domain (`rinnai`) has not changed.

---

## Which Version Are You Migrating From?

v2.0.0 supports automatic migration from **two different legacy versions**:

| Legacy Version | Connection Type | Config Data | Migration Result |
|----------------|-----------------|-------------|------------------|
| **v1.5.x** | Cloud API | Email + Tokens | → Cloud mode |
| **v2.1.x** | Local only | Host IP address | → Local mode |

### Migrating from v1.5.x (Cloud Version)

If you were using the **cloud API version** (email/password login):

- ✅ **If your tokens are still valid**: Migration happens automatically
- ⚠️ **If your tokens have expired**: You'll see a "Re-authentication required" error
  - Go to **Settings** → **Devices & Services** → **Rinnai** → **Reconfigure**
  - Enter your Rinnai credentials to complete migration

### Migrating from v2.1.x (Local-Only Version)

If you were using the **local-only version** (just IP address):

- ✅ Migration happens automatically - your host IP is preserved
- The integration will be set to **Local mode**
- You can optionally add cloud credentials later via **Reconfigure** to enable Hybrid mode

---

## Migration Instructions

### Option 1: Clean Install (Recommended)

This is the safest and recommended approach:

#### Step 1: Remove the Old Integration

1. Go to **Settings** → **Devices & Services**
2. Find **Rinnai Control-R Water Heater** and click on it
3. Click the **⋮** (three dots menu) → **Delete**
4. Confirm the deletion

#### Step 2: Remove Old Files via HACS

1. Go to **HACS** → **Integrations**
2. Find **Rinnai Control-R Water Heater**
3. Click the **⋮** (three dots menu) → **Remove**
4. Confirm the removal

#### Step 3: Manually Delete Old Directory (if exists)

After removing via HACS, verify the old directory is gone. If it still exists, manually delete it:

**Using File Editor Add-on or SSH:**
```bash
rm -rf /config/custom_components/rinnaicontrolr-ha
```

**Using Samba/Network Share:**
Navigate to your Home Assistant config folder and delete the `custom_components/rinnaicontrolr-ha` directory.

#### Step 4: Restart Home Assistant

1. Go to **Settings** → **System** → **Restart**
2. Click **Restart** and wait for Home Assistant to fully restart

#### Step 5: Install v2.0.0

1. Go to **HACS** → **Integrations**
2. Click **+ Explore & Download Repositories**
3. Search for **Rinnai Control-R Water Heater**
4. Click **Download**
5. Select version **2.0.0** (or latest)
6. Click **Download**

#### Step 6: Restart Home Assistant Again

1. Go to **Settings** → **System** → **Restart**
2. Click **Restart**

#### Step 7: Re-add the Integration

1. Go to **Settings** → **Devices & Services**
2. Click **+ Add Integration**
3. Search for **Rinnai Control-R Water Heater**
4. Follow the configuration wizard

---

### Option 2: In-Place Migration (Advanced)

For users comfortable with manual file operations:

#### Step 1: Create a Backup

1. Go to **Settings** → **System** → **Backups**
2. Click **Create Backup**
3. Wait for the backup to complete

#### Step 2: Stop Home Assistant

Stop Home Assistant before modifying files to prevent conflicts.

**Using SSH or Terminal:**
```bash
ha core stop
```

#### Step 3: Rename the Directory

**Using SSH or Terminal:**
```bash
mv /config/custom_components/rinnaicontrolr-ha /config/custom_components/rinnai
```

**Using File Editor:**
1. Navigate to `/config/custom_components/`
2. Rename the `rinnaicontrolr-ha` folder to `rinnai`

#### Step 4: Update HACS Tracking (Optional)

If HACS is confused about the installation, you may need to:
1. Remove the old repository reference in HACS
2. Re-add the repository to track updates

#### Step 5: Start Home Assistant

**Using SSH or Terminal:**
```bash
ha core start
```

#### Step 6: Verify Installation

1. Go to **Settings** → **Devices & Services**
2. Confirm **Rinnai Control-R Water Heater** appears and is working
3. Check that all your entities are available

---

## What's New in v2.0.0

### New Features

- **Local Connection Mode**: Direct TCP connection to water heater (port 9798) for faster, more reliable control
- **Hybrid Mode**: Local primary with automatic cloud fallback
- **New Sensors**: Outlet/inlet temperature, water flow rate, combustion cycles, fan current/frequency, and more
- **Binary Sensors**: Heating status and recirculation status
- **Recirculation Switch**: Toggle control with configurable duration
- **Multi-language Support**: 14 languages supported
- **Proactive Token Refresh**: Credentials refresh before expiration
- **Dynamic Device Discovery**: New devices discovered without reload

### Configuration Options

After upgrading, configure the new options via **Settings** → **Devices & Services** → **Rinnai Control-R Water Heater** → **Configure**:

| Option | Description | Default |
|--------|-------------|---------|
| Connection Mode | Cloud, Local, or Hybrid | Cloud |
| Enable Maintenance Data | Retrieves detailed sensor data every 5 minutes | Off |
| Recirculation Duration | Default duration for recirculation switch (5-300 min) | 10 min |

---

## Troubleshooting

### HACS Shows Duplicate Entries

If you see both old and new entries in HACS:
1. Remove the old entry from HACS
2. Ensure only `custom_components/rinnai/` exists (not `rinnaicontrolr-ha`)
3. Restart Home Assistant

### Entities Missing After Migration

If entities are missing after migration:
1. Go to **Settings** → **Devices & Services**
2. Click on **Rinnai Control-R Water Heater**
3. Verify your devices are listed
4. If not, try removing and re-adding the integration

### "Integration Not Found" Error

If Home Assistant can't find the integration:
1. Verify the directory is named exactly `rinnai` (lowercase, no hyphens)
2. Ensure all files are present in `custom_components/rinnai/`
3. Check the Home Assistant logs for errors
4. Restart Home Assistant

### Automations/Scripts Broken

Your automations and scripts should continue to work since entity IDs are based on the domain (`rinnai`) which hasn't changed. If you experience issues:
1. Go to **Developer Tools** → **States**
2. Search for `rinnai` to see all current entities
3. Update any automations that reference old entity IDs

---

## Getting Help

If you encounter issues during migration:

1. **Check the logs**: Go to **Settings** → **System** → **Logs** and search for "rinnai"
2. **Open an issue**: [GitHub Issues](https://github.com/explosivo22/rinnaicontrolr-ha/issues)
3. **Include details**: Home Assistant version, installation method, and any error messages

---

## Rollback Instructions

If you need to rollback to v1.x.x:

1. Remove the v2.0.0 integration and files
2. Download the last v1.x.x release from [GitHub Releases](https://github.com/explosivo22/rinnaicontrolr-ha/releases)
3. Extract to `custom_components/rinnaicontrolr-ha/`
4. Restart Home Assistant
5. Re-add the integration
