from decimal import Decimal
from typing import Annotated, Optional
from pydantic import BaseModel, Field, field_validator, PlainSerializer

DecimalJsonAsFloat = Annotated[
    Decimal,
    PlainSerializer(lambda v: float(v), return_type=float, when_used='json')
]

class ProductInput(BaseModel):
    """
    Representa o contrato de entrada (Schema) para criação e atualização de produtos.
    Garante tipo, tamanho e integridade dos dados na borda da aplicação.
    """
    title: str = Field(
        min_length=1,
        max_length=200,
        description="Título do produto no catálogo."
    )
    category: str = Field(
        min_length=1,
        description="Categoria principal do produto para indexação e buscas."
    )
    description: str = Field(
        min_length=1,
        max_length=1000,
        description="Descrição detalhada das especificações técnicas do produto."
    )
    price: Decimal = Field(
        gt=0,
        max_digits=10,
        decimal_places=2,
        description="Preço unitário em Decimal para precisão em cálculos financeiros."
    )

    @field_validator('price')
    @classmethod
    def price_must_bee_positive(cls, value: Decimal) -> Decimal:
        """Validação customizada para garantir consistência financeira."""
        if value <= 0:
            raise ValueError('O preço do produto deve ser estritamente maior que zero.')
        return value

    @field_validator('category')
    @classmethod
    def category_must_be_valid(cls, value: str) -> str:
        """Garante que o produto pertença a uma das categorias permitidas no inventário."""
        valid_categories = ['Electronics', 'Audio', 'Computers', 'Accessories', 'Home']
        if value not in valid_categories:
            raise ValueError(
                f"Categoria inválida: '{value}'. Categorias permitidas: {valid_categories}"
            )
        return value

class ProductUpdateInput(BaseModel):
    """
    Representa o contrato de entrada (Schema) para ATUALIZAÇÃO de produtos.
    Todos os campos são opcionais, mas se forem enviados, devem passar nas mesmas validações.
    """
    title: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=200,
        description="Novo título do produto."
    )
    category: Optional[str] = Field(
        default=None,
        min_length=1,
        description="Nova categoria do produto."
    )
    description: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=1000,
        description="Nova descrição do produto."
    )
    price: Optional[DecimalJsonAsFloat] = Field(
        default=None,
        gt=0,
        max_digits=10,
        decimal_places=2,
        description="Novo preço do produto."
    )

    @field_validator('price')
    @classmethod
    def price_must_be_positive_if_present(cls, value: Optional[Decimal]) -> Optional[Decimal]:
        if value is not None and value <= 0:
            raise ValueError('O preço do produto deve ser estritamente maior que zero.')
        return value

    @field_validator('category')
    @classmethod
    def category_must_be_valid_if_present(cls, value: Optional[str]) -> Optional[str]:
        if value is not None:
            valid_categories = ['Electronics', 'Audio', 'Computers', 'Accessories', 'Home']
            if value not in valid_categories:
                raise ValueError(
                    f"Categoria inválida: '{value}'. Categorias permitidas: {valid_categories}"
                )
        return value