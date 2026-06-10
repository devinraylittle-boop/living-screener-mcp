from __future__ import annotations

from app.config import Settings, get_settings
from app.data_adapters.factory import create_market_data_adapter
from app.services.backtest_service import BacktestService
from app.services.crypto_paper_service import CryptoPaperService
from app.services.debug_validation_service import DebugValidationService
from app.services.evidence_packet_service import EvidencePacketService
from app.services.global_research_service import GlobalResearchService
from app.services.journal_service import JournalService
from app.services.learning_service import LearningService
from app.services.options_service import OptionsService
from app.services.pending_order_service import PendingOrderService
from app.services.premove_blueprint_service import PreMoveBlueprintService
from app.services.postmortem_service import PostmortemService
from app.services.prompt_service import PromptService
from app.services.review_outcome_service import ReviewOutcomeService
from app.services.risk_service import RiskService
from app.services.scanner_service import ScannerService
from app.storage.database import Database
from app.storage.repositories import EventRepository, RecommendationRepository


class ServiceContainer:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.database = Database(self.settings.database_path)
        self.events = EventRepository(self.database)
        self.recommendations = RecommendationRepository(self.database)
        self.market_data = create_market_data_adapter(self.settings)
        self.scanner = ScannerService(self.settings, self.events, self.recommendations, self.market_data)
        self.risk = RiskService(self.settings, self.events)
        self.journal = JournalService(self.events)
        self.options = OptionsService(self.settings, self.events)
        self.pending_orders = PendingOrderService(self.settings, self.events, self.scanner, self.options)
        self.backtest = BacktestService(self.events, self.settings)
        self.crypto_paper = CryptoPaperService(self.events)
        self.global_research = GlobalResearchService(self.events)
        self.review_outcomes = ReviewOutcomeService(self.settings, self.events, self.market_data)
        self.learning = LearningService(self.events)
        self.postmortem = PostmortemService(self.events)
        self.prompt = PromptService(self.events)
        self.premove_blueprint = PreMoveBlueprintService(self.events)
        self.evidence_packets = EvidencePacketService(self.events)
        self.debug_validation = DebugValidationService(self)


def create_container(settings: Settings | None = None) -> ServiceContainer:
    return ServiceContainer(settings)
