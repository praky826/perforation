Phase 16 Completion Summary: Frontend Category F - Session Continuity

Phase 16 adds frontend/dialogs/resume_session_dialog.py and frontend/dialogs/reset_confirm_dialog.py, and extends frontend/tabs/processing_tab.py with resume and reprocess actions.

ResumeSessionDialog checks for an incomplete session and routes the selected session to backend.api.resume_session through frontend.client.Client. ResetConfirmDialog routes session deletion to backend.api.reset_session. ProcessingTab now requests session resume and reprocessing from a selected stage while retaining its Phase 12 status, progress, and manifest refresh behavior.

The frontend contains no direct session-directory I/O and does not implement pipeline execution. A focused import and method-presence test is provided in tests/test_phase16_frontend.py. Phase 17 remains pending.
