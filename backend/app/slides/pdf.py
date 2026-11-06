"""PDF: headless Chromium prints the frontend's print page of a presentation.

Ported from blattwerk's pdf.py, without its render token: this app has no accounts, Caddy's
shared password guards every page, and Chromium reaches the frontend inside the Docker network.
"""

import asyncio
import os
import re
import sqlite3
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Response
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import TimeoutError as PlaywrightTimeout
from playwright.async_api import async_playwright

from app.slides import db
from app.slides.presentations import find

router = APIRouter(prefix="/api/slides")
Con = Annotated[sqlite3.Connection, Depends(db.con)]
FRONTEND = os.environ.get("FRONTEND_INTERNAL_URL", "http://localhost:3000")
# Each print is a Chromium: two at once, the rest wait their turn.
SLOTS = asyncio.Semaphore(2)
# Milliseconds the print page may take to draw, fonts and pictures included.
WAIT = 30000


@router.get("/presentations/{pid}/pdf")
async def pdf(pid: int, con: Con) -> Response:
    title = find(con, pid)["title"]
    async with SLOTS, async_playwright() as p:
        browser = await p.chromium.launch(args=["--disable-dev-shm-usage", "--no-sandbox"])
        try:
            page = await browser.new_page()
            await page.goto(f"{FRONTEND}/print/{pid}")
            await page.wait_for_function("window.__slidesReady === true", timeout=WAIT)
            data = await page.pdf(
                width="13.333in", height="7.5in", print_background=True, prefer_css_page_size=True
            )
        except PlaywrightTimeout:
            raise HTTPException(504, "The print page did not finish drawing.") from None
        except PlaywrightError as e:
            raise HTTPException(502, f"Could not print the presentation: {e.message}") from None
        finally:
            await browser.close()
    name = re.sub(r'[\\/:*?"<>|]+', "", title).strip() or "presentation"
    return Response(
        data,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(name)}.pdf"},
    )
