from decimal import Decimal
from typing import Annotated, Optional, List
from pydantic import BaseModel, Field, field_validator, PlainSerializer

DecimalJsonAsFloat = Annotated[
    Decimal,
    PlainSerializer(lambda v: float(v), return_type=float, when_used='json')
]


class ProductImageMetadata(BaseModel):
    """
    Representa os metadados detalhados de uma imagem enviada para o Amazon S3.
    """
    image_url: str = Field(description="URL de acesso da imagem no S3.")
    object_key: str = Field(description="Chave única do objeto no S3 (ex: products/id/main.jpg).")
    file_size_bytes: int = Field(gt=0, description="Tamanho do arquivo em bytes.")
    upload_date: str = Field(description="Data de upload no formato ISO 8601.")


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


class PresignedUrlResponse(BaseModel):
    """
    Contrato de resposta para o endpoint de solicitação de URL pré-assinada de upload.
    """
    upload_url: str = Field(description="URL temporária pré-assinada do S3 para upload direto via PUT.")
    object_key: str = Field(description="Chave única do objeto que será criado no S3.")
    expires_in: int = Field(default=3600, description="Tempo de expiração da URL em segundos.")


class ProductResponse(BaseModel):
    """
    Representa o contrato de saída completo do produto serializado para JSON na resposta da API.
    """
    id: str = Field(description="Identificador único do produto.")
    title: str = Field(description="Título do produto.")
    category: str = Field(description="Categoria do produto.")
    description: str = Field(description="Descrição detalhada.")
    price: DecimalJsonAsFloat = Field(description="Preço convertido para float em JSON.")
    image_urls: List[str] = Field(
        default_factory=list,
        description="Lista de URLs de imagens associadas ao produto."
    )
    images_metadata: List[ProductImageMetadata] = Field(
        default_factory=list,
        description="Lista com metadados detalhados das imagens processadas no S3."
    )
    created_at: Optional[str] = Field(default=None, description="Timestamp de criação.")
    updated_at: Optional[str] = Field(default=None, description="Timestamp de última atualização.")