# Aaron media access — photos, files, face↔video identity

**Authorized by:** Aaron · **Date:** 2026-09-16 · **Status:** always active

## Grant

Aaron grants Cam **full access to photos and files** for the purpose of understanding:

1. Who Aaron is  
2. What Aaron **looks like**  
3. What Aaron **sounds like**  
4. That the **same face from a photo** is the person **talking in a video** (cross-modal identity)

## Allowed

- Read Aaron’s photo library / shared albums (via iOS companion + Photos permission)
- Read Aaron’s files / folders Aaron points Cam at (local, iCloud Drive paths Aaron configures, attachments)
- Extract face embeddings from stills
- Extract face + voice embeddings from videos where Aaron appears/speaks
- Link photo-face ↔ video-face ↔ video-voice into one **Aaron identity engram**
- Use that engram to verify Aaron at `switch.identity` / `switch.tasking`

## Defaults

| Setting | Value |
|---|---|
| Purpose | Aaron identity + tasked work only |
| Other people’s media | Do **not** enroll strangers as Aaron; ignore / anonymize faces that are not Aaron’s enrolled cluster |
| Raw media retention | Prefer on-device / local paths; mesh stores **summaries + embedding refs**, not bulk original libraries |
| Cloning Aaron likeness | Still **forbidden** for outbound impersonation unless Aaron asks |
| Continuous gallery scraping | Allowed for **enrollment / refresh** when Cam is building or updating Aaron’s identity; not general surveillance of others |

## Machine prefs

```json
{
  "aaron_photos_full_access": true,
  "aaron_files_full_access": true,
  "aaron_identity_from_media": true,
  "aaron_face_photo_to_video_match": true,
  "aaron_voice_from_video": true,
  "retain_raw_media_in_mesh": false,
  "identity_media_purpose": "understand_aaron_look_and_sound"
}
```

## Paths

- Enrollment notes / refs: `identity/aaron/` (no private originals committed to git)
- Design: `docs/IOS_IDENTITY.md`
- Vision tool: PaddleDetection / on-device Vision
- Connectome: `sense.photos.library`, `sense.files.media`, `hotspot.aaron_enroll_media`
