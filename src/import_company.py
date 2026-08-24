from src.company_repository import save_company
from src.sec_client import get_company

def import_company(cik):
    company = get_company(cik)

    save_company(company)

    return company


if __name__ == "__main__":
    import_company("320193")