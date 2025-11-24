from data_analysis_agent import DataAnalysisAgent
from config.llm_config import LLMConfig

def main():
    llm_config = LLMConfig()
    agent = DataAnalysisAgent(llm_config)
    files = ["./comp-demo-data.csv"]
    report = agent.analyze(user_input="provide analysis on AVERAGE of Base Pay over different Pay Zone, separated by different tenure group.",files=files)
    print(report)
    
if __name__ == "__main__":
    main()
    