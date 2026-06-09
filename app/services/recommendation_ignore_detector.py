import math
from typing import Dict, Any, List, Set, Union, Tuple

class RecommendationIgnoreDetector:
    """
    RecommendationIgnoreDetector
    ============================
    Detects when a recommended test suite was effectively ignored by the developer.
    
    Uses statistical confidence intervals (Wilson Score Interval) to conservatively
    handle tiny test suites (< 5 tests) to avoid false positives.
    """
    
    @staticmethod
    def calculate_wilson_score_interval(x: int, n: int, confidence_level: float = 0.90) -> Tuple[float, float]:
        """
        Calculate the Wilson Score Interval for a given success count x and total trials n.
        
        Args:
            x: Number of recommended tests executed.
            n: Total number of recommended tests.
            confidence_level: The confidence level (default: 0.90).
            
        Returns:
            A tuple (lower_bound, upper_bound).
        """
        if n <= 0:
            return 0.0, 0.0
            
        p_hat = x / n
        
        # Determine z-score based on confidence level
        if confidence_level == 0.90:
            z = 1.64485
        elif confidence_level == 0.95:
            z = 1.95996
        else:
            # Fallback/default to 90%
            z = 1.64485
            
        z2 = z ** 2
        denominator = 1 + z2 / n
        center = (p_hat + z2 / (2 * n)) / denominator
        spread = z * math.sqrt((p_hat * (1 - p_hat) / n) + z2 / (4 * n ** 2)) / denominator
        
        lower_bound = max(0.0, center - spread)
        upper_bound = min(1.0, center + spread)
        
        return lower_bound, upper_bound

    @classmethod
    def detect(
        cls, 
        recommended_tests: Union[List[Any], Set[Any]], 
        executed_tests: Union[List[Any], Set[Any]],
        confidence_level: float = 0.90
    ) -> Dict[str, Any]:
        """
        Analyze recommended vs executed tests to detect if recommendations were ignored.
        
        Args:
            recommended_tests: The collection of recommended tests.
            executed_tests: The collection of executed tests.
            confidence_level: The statistical confidence level for tiny suites.
            
        Returns:
            A dictionary containing the detection results:
            - is_presented: bool (True if there are recommended tests)
            - total_recommended: int (count of recommended tests)
            - total_executed: int (count of executed tests)
            - executed_recommended: int (count of recommended tests that were executed)
            - overlap_ratio: float (raw proportion of recommended tests that were executed)
            - adjusted_overlap_ratio: float (adjusted ratio for conservative handling of tiny suites)
            - status: str (FULLY_FOLLOWED, PARTIALLY_FOLLOWED, or IGNORED)
            - is_tiny: bool (True if recommended tests count is < 5)
            - confidence_interval: Tuple[float, float] (Wilson lower and upper bounds)
        """
        rec_set = set(recommended_tests)
        exec_set = set(executed_tests)
        
        n = len(rec_set)
        if n == 0:
            return {
                "is_presented": False,
                "total_recommended": 0,
                "total_executed": len(exec_set),
                "executed_recommended": 0,
                "overlap_ratio": 0.0,
                "adjusted_overlap_ratio": 0.0,
                "status": "NOT_APPLICABLE",
                "is_tiny": False,
                "confidence_interval": (0.0, 0.0)
            }
            
        # x is the overlap count
        x = len(rec_set.intersection(exec_set))
        raw_ratio = x / n
        
        is_tiny = n < 5
        
        # Calculate confidence interval
        lower, upper = cls.calculate_wilson_score_interval(x, n, confidence_level=confidence_level)
        
        # Adjusted ratio selection:
        # If it's a tiny suite, handle conservatively using the upper bound of the confidence interval
        # to minimize false positives (except when absolute zero overlap exists, i.e., x == 0)
        if is_tiny:
            if x == 0:
                adjusted_ratio = 0.0
            else:
                adjusted_ratio = upper
        else:
            adjusted_ratio = raw_ratio
            
        # Determine status based on thresholds
        if adjusted_ratio >= 0.90:
            status = "FULLY_FOLLOWED"
        elif adjusted_ratio >= 0.40:
            status = "PARTIALLY_FOLLOWED"
        else:
            status = "IGNORED"
            
        return {
            "is_presented": True,
            "total_recommended": n,
            "total_executed": len(exec_set),
            "executed_recommended": x,
            "overlap_ratio": round(raw_ratio, 6),
            "adjusted_overlap_ratio": round(adjusted_ratio, 6),
            "status": status,
            "is_tiny": is_tiny,
            "confidence_interval": (round(lower, 6), round(upper, 6))
        }
