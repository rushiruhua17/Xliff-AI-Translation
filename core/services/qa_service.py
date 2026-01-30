from typing import List, Tuple
from core.qa import QAChecker
from core.xliff_obj import TranslationUnit

class QAService:
    """
    Encapsulates QA logic to decouple it from UI.
    Provides methods to run QA checks on translation units.
    """
    def __init__(self):
        self.checker = QAChecker()

    @staticmethod
    def check_batch(units: List[TranslationUnit]) -> Tuple[int, int]:
        """
        Static method to run QA check on a batch of units.
        Convenience wrapper around run_qa.
        """
        service = QAService()
        return service.run_qa(units)

    def run_qa(self, units: List[TranslationUnit]) -> Tuple[int, int]:
        """
        Runs QA check on all units.
        Updates unit properties in-place (this is acceptable as it's a synchronous operation usually triggered by UI).
        Returns (error_count, warning_count).
        """
        error_count = 0
        warning_count = 0
        
        for unit in units:
            if unit.state == "locked": continue
            
            result = self.checker.check_unit(
                unit.source_abstracted, 
                unit.target_abstracted, 
                unit.state
            )
            
            unit.qa_status = result.status
            unit.tag_stats = result.tag_stats
            unit.qa_details = result.qa_details
            unit.errors = [issue.message for issue in result.issues]
            
            if result.status == "error":
                error_count += 1
            elif result.status == "warning":
                warning_count += 1
                
        return error_count, warning_count

    def get_readiness_stats(self, units: List[TranslationUnit]) -> Tuple[int, int, int]:
        """
        Returns stats for readiness panel: (error_count, warning_count, health_score)
        """
        error_count = 0
        warning_count = 0
        total_active = 0
        
        for unit in units:
            if unit.state == "locked": continue
            total_active += 1
            if unit.qa_status == "error":
                error_count += 1
            elif unit.qa_status == "warning":
                warning_count += 1
        
        if total_active > 0:
            health = max(0, 100 - (error_count * 5) - (warning_count * 1))
        else:
            health = 100
            
        return error_count, warning_count, health
