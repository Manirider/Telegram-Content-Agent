"""Google Sheets client."""
import base64
import json

import gspread
from google.oauth2.service_account import Credentials

from app.sheets.schemas import REQUIRED_HEADERS, SheetsConfig, SheetsRow
from app.utils.exceptions import ConfigurationError, SheetsError
from app.utils.logging import get_logger
from app.utils.retry import async_retry

logger = get_logger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


class SheetsClient:
    """Google Sheets API client."""
    
    def __init__(self, config: SheetsConfig):
        self.config = config
        self.gc: gspread.Client | None = None
        self.worksheet: gspread.Worksheet | None = None
    
    def _decode_credentials(self) -> dict:
        """Decode base64 credentials."""
        try:
            decoded = base64.b64decode(self.config.credentials_b64).decode("utf-8")
            return json.loads(decoded)
        except Exception as e:
            raise ConfigurationError(f"Failed to decode Google credentials: {e}") from e
    
    async def authenticate(self) -> None:
        """Authenticate with Google Sheets API."""
        try:
            creds_dict = self._decode_credentials()
            credentials = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
            self.gc = gspread.authorize(credentials)
            logger.info("Google Sheets authenticated")
        except Exception as e:
            raise SheetsError(f"Authentication failed: {e}") from e
    
    async def ensure_worksheet(self) -> gspread.Worksheet:
        """Ensure worksheet exists with correct headers."""
        if not self.gc:
            await self.authenticate()
        
        try:
            spreadsheet = self.gc.open_by_key(self.config.spreadsheet_id)  # type: ignore[union-attr]
        except gspread.SpreadsheetNotFound as e:
            raise SheetsError(f"Spreadsheet not found: {self.config.spreadsheet_id}") from e
        except Exception as e:
            raise SheetsError(f"Failed to open spreadsheet: {e}") from e
        
        try:
            self.worksheet = spreadsheet.worksheet(self.config.worksheet_name)
        except gspread.WorksheetNotFound:
            # Create worksheet
            self.worksheet = spreadsheet.add_worksheet(
                title=self.config.worksheet_name,
                rows=1000,
                cols=len(REQUIRED_HEADERS),
            )
            logger.info("Created new worksheet", name=self.config.worksheet_name)
        
        # Ensure headers
        await self._ensure_headers()
        
        return self.worksheet
    
    async def _ensure_headers(self) -> None:
        """Ensure worksheet has correct headers."""
        if not self.worksheet:
            return
        
        try:
            existing_headers = self.worksheet.row_values(1)  # type: ignore[union-attr]
            if existing_headers != REQUIRED_HEADERS:
                # Update headers
                self.worksheet.update("A1", [REQUIRED_HEADERS])  # type: ignore[union-attr,arg-type]
                logger.info("Updated worksheet headers")
        except (OSError, RuntimeError, gspread.GSpreadException) as e:
            logger.warning("Could not verify/update headers", error=str(e))
    
    async def append_row(self, row: SheetsRow) -> None:
        """Append a row to the worksheet."""
        if not self.worksheet:
            await self.ensure_worksheet()
        
        await async_retry(
            self._append_row_internal,
            row,
            max_attempts=3,
            base_delay=1.0,
            max_delay=30.0,
        )
    
    async def _append_row_internal(self, row: SheetsRow) -> None:
        """Internal append with error classification."""
        try:
            self.worksheet.append_row(row.to_list(), value_input_option="USER_ENTERED")  # type: ignore[union-attr,arg-type]
        except Exception as e:
            error_str = str(e).lower()
            if "rate limit" in error_str or "429" in error_str:
                from app.utils.exceptions import RateLimitError
                raise RateLimitError("Sheets rate limit") from e
            if "quota" in error_str:
                from app.utils.exceptions import RateLimitError
                raise RateLimitError("Sheets quota exceeded") from e
            raise SheetsError(f"Sheets API error: {e}") from e
    
    async def get_existing_fingerprints(self) -> list[str]:
        """Get existing source identifiers for duplicate checking.
        
        Note: This fetches only the SourceIdentifier column (A) for efficiency.
        """
        if not self.worksheet:
            await self.ensure_worksheet()
        
        try:
            # Get all values from column A (SourceIdentifier)
            # Skip header row
            col_values = self.worksheet.col_values(1)  # type: ignore[union-attr]
            result = col_values[1:] if len(col_values) > 1 else []
            return [str(v) for v in result]  # type: ignore[return-value]
        except (OSError, RuntimeError, gspread.GSpreadException) as e:
            logger.warning("Failed to fetch existing fingerprints", error=str(e))
            return []
    
    async def check_duplicate(self, fingerprint: str) -> bool:
        """Check if fingerprint already exists in sheet."""
        existing = await self.get_existing_fingerprints()
        return fingerprint in existing
    
    async def close(self) -> None:
        """Close client."""
        self.gc = None
        self.worksheet = None