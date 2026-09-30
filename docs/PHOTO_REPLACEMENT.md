# Replacing the illustrative photographs

Six AI-generated editorial scenes are used as temporary illustrations. They are not actual COCEGN activities, staff or beneficiaries. Each figure is labelled on the website. No generated image is presented as the founder's portrait or an individual sponsorship profile.

All displayed images are local WebP assets in `assets/img/photos/`. Each photo has a 640px and 1200px version; browsers choose the appropriate size. Lower-page images load lazily. `manifest.json` lists every page using each image.

| Photo key | Intended real replacement |
| --- | --- |
| `educators-community` | Educators together at a real COCEGN gathering |
| `academy-classroom` | A classroom at COCEGN Academy, with appropriate permissions |
| `teacher-preparing` | An educator preparing or teaching, with permission |
| `family-support` | A real family-support activity, with adult consent |
| `aged-companion` | A companion visiting an aged educator, with both adults' consent |
| `educator-workshop` | A real fellowship, workshop, conference or training session |

## Replace an image across every page

1. Get permission for public use, including guardian permission for children. Keep written consent outside the public website directory.
2. Export two landscape 3:2 WebP files: approximately **640 × 427** and **1200 × 800**. Aim for less than 200 KB for the large version. Do not just rename a JPG extension.
3. Run the command below, supplying your actual paths, accurate description and credit. The script requires only Python's standard library.

```bash
python3 scripts/replace_photo.py academy-classroom \
  --small /path/to/real-classroom-640.webp \
  --large /path/to/real-classroom-1200.webp \
  --alt "Accurate description of the real classroom photograph" \
  --caption "Accurate activity, location and photographer credit"
```

The command replaces the two files, updates alt text and captions on every listed page, and changes the manifest's `illustrative` flag to `false`. Review the pages at phone and desktop widths because hero banners crop images differently from content cards. Commit the image and HTML changes together.

For a photo needed in only one place, add a separately named image instead of replacing a shared key. The founder section currently uses initials; replace that element with a real authorised founder portrait when available. Keep synthetic illustrations out of actual beneficiary profiles.
