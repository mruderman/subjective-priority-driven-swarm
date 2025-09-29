    class FallbackSubjectiveAssessment:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)
        
        def model_dump(self):
            """Provide compatibility with Pydantic models"""
            return {
                "importance_to_self": self.importance_to_self,
                "urgency": self.urgency,
                "importance_to_group": self.importance_to_group
            }
