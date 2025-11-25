from data_analysis_agent import DataAnalysisAgent
from config.llm_config import LLMConfig

def main():
    llm_config = LLMConfig()
    agent = DataAnalysisAgent(llm_config)
    files = ["./comp-demo-data.csv"]
    report = agent.analyze(user_input="what is the average base pay for M2 in USA zone 1?",files=files)
    print(report)
    
if __name__ == "__main__":
    main()
    