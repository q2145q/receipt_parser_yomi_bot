# Changelog

Все значимые изменения в этом проекте будут документированы в этом файле.

Формат основан на [Keep a Changelog](https://keepachangelog.com/ru/1.0.0/),
и этот проект следует [Semantic Versioning](https://semver.org/lang/ru/).

## [Unreleased]

### Added
- Comprehensive documentation (ARCHITECTURE.md, API.md, USAGE.md)
- CONTRIBUTING.md with development guidelines
- CHANGELOG.md for tracking changes

### Changed
- Updated requirements.txt with missing dependencies (openai, pdf2image, pytesseract, numpy)
- Fixed README.md duplicate content and added documentation links

### Removed
- Removed unused fns_api.py module
- Removed empty token.json placeholder file

## [1.0.0] - Initial Release

### Added
- Telegram bot interface for receipt processing
- OpenAI GPT-4o-mini Vision API integration for data extraction
- QR code parsing with pyzbar
- OCR fallback with Tesseract
- Google Drive integration with structured folder organization
- Google Sheets integration for data storage
- Support for single photo processing
- Support for photo album processing (batch mode)
- Support for PDF receipt processing
- Interactive confirmation with inline buttons
- Automatic folder structure creation (INN/Month-Year)
- Environment-based configuration

### Features
- 📸 Single receipt photo processing
- 📸📸📸 Batch processing via photo albums
- 📄 PDF file support
- 🔗 FNS receipt link parsing
- 🤖 Automatic data extraction via AI
- 📊 Google Sheets integration
- 📁 Structured Google Drive storage
- ✅ User confirmation before saving

### Extracted Data
- Full name (Фамилия И.О.)
- Amount with currency symbol
- Service description
- Seller INN (12 digits)
- Buyer INN (10 or 12 digits)
- Receipt date (dd.mm.yyyy format)
- Status (Active/Cancelled)
- FNS receipt URL

### Technology Stack
- Python 3.12
- python-telegram-bot 20.7
- OpenAI GPT-4o-mini Vision API
- Google Drive API v3
- Google Sheets API v4
- pyzbar for QR code decoding
- opencv-python for image processing
- pytesseract for OCR
- pdf2image for PDF conversion

### Cost
- OpenAI: ~$0.0003 per receipt (~₽0.03)
- Google APIs: Free (within quotas)
- Telegram Bot API: Free

## Project Milestones

### Phase 1: MVP ✅
- [x] Basic receipt processing
- [x] OpenAI Vision integration
- [x] Google Drive upload
- [x] Google Sheets storage
- [x] Telegram bot interface

### Phase 2: Enhancement ✅
- [x] Album/batch processing
- [x] PDF support
- [x] QR code parsing
- [x] Interactive confirmation

### Phase 3: Documentation ✅
- [x] Architecture documentation
- [x] API reference
- [x] Usage guide
- [x] Contributing guidelines
- [x] Changelog

### Phase 4: Future (Planned)
- [ ] Unit and integration tests
- [ ] Data editing via inline keyboard
- [ ] Export to Excel/CSV
- [ ] Statistics and analytics
- [ ] Docker containerization
- [ ] Multi-language support
- [ ] Web interface
- [ ] Integration with accounting systems

## Notes

### Breaking Changes
None yet (initial release).

### Deprecations
None yet (initial release).

### Security
- All secrets stored in environment variables
- OAuth 2.0 for Google API authentication
- No hardcoded credentials
- .gitignore properly configured

### Known Issues
- No automated tests yet
- In-memory storage for pending receipts (should use Redis/DB for production)
- No retry mechanism for API failures
- Limited error recovery

### Dependencies
See [requirements.txt](requirements.txt) for full list.

### System Requirements
- Python 3.12+
- libzbar0 (QR code library)
- tesseract-ocr (OCR engine)
- poppler-utils (PDF conversion)
- Internet connection

### Environment Variables Required
- `TELEGRAM_BOT_TOKEN` - Telegram Bot API token
- `GOOGLE_DRIVE_FOLDER_ID` - Google Drive root folder ID
- `GOOGLE_SHEET_ID` - Google Sheets spreadsheet ID
- `OPENAI_API_KEY` - OpenAI API key

## Contributors

- Миша Абрамян - Initial development

## License

MIT License - see LICENSE file for details.

---

**Note:** For detailed usage instructions, see [USAGE.md](USAGE.md).  
For technical architecture, see [ARCHITECTURE.md](ARCHITECTURE.md).  
For API reference, see [API.md](API.md).
