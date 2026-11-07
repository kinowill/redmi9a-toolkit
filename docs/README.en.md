# Redmi 9A Community Toolkit

Portable Python tooling for device identification, bounded image extraction,
SHA256 checks, reviewed Android GSI installation plans, guarded MediaTek
bootloader unlock and post-boot verification. See the root README for commands.

Current reference: Redmi 9A M2006C3LG, dandelion, 2GB/32GB, MIUI EEA
V12.0.17.0.QCDEUXM vendor, ARM32 userspace / ARM64 kernel / 64-bit binder / SAR.
The manual reference installation booted LineageOS 20 Android 13 with Magisk and
Termux. The newly written read-only commands were tested against that phone.
New write workflows have simulated-transport tests and remain hardware-unvalidated.

This is an experimental toolkit, not a universal ROM installer. Keep a suitable
stock recovery path and back up important data. Preparing and auditing images
is still required. Unlocking/flashing can erase data or brick a device.
Never relock the bootloader with the reference custom images.

No firmware, private logs, device identifiers, ADB keys or patched device images
are distributed. Bundle attestations do not establish image safety. SHA256
establishes integrity only when the expected digest is trusted independently.

Other models, firmware bases, Android versions and native Linux ports need
their own reviewed profiles and hardware validation. Native Linux cannot simply
autodetect all Android phone drivers. The dandelion Droidian image project has
withdrawn builds after reported bricks on hardware revisions.

GPL-3.0-or-later. See CONTRIBUTING.md, SECURITY.md and docs/VALIDATED_DEVICE.md.
