"""Shared pytest fixtures and mocks."""

import pytest
from unittest.mock import MagicMock, patch

from src.models import Chunk


@pytest.fixture
def sample_ada_spec():
    """Small Ada spec file content."""
    return """with Interfaces;

package Basic_Types is
   subtype Byte is Interfaces.Unsigned_8
      with Object_Size => 8, Value_Size => 8;
   type Byte_Array is array (Natural range <>) of Byte;
end Basic_Types;
"""


@pytest.fixture
def sample_ada_body():
    """Small Ada body file content."""
    return """package body Component.Ccsds_Echo.Implementation is

   overriding procedure Ccsds_Space_Packet_T_Recv_Sync (
      Self : in out Instance;
      Arg : in Ccsds_Space_Packet.T
   ) is
   begin
      Self.Packet_T_Send_If_Connected (
         Self.Packets.Echo_Packet_Truncate (Self.Sys_Time_T_Get, Arg)
      );
   end Ccsds_Space_Packet_T_Recv_Sync;

end Component.Ccsds_Echo.Implementation;
"""


@pytest.fixture
def sample_large_ada():
    """Large Ada file that should be split into multiple chunks."""
    procedures = []
    for i in range(20):
        procedures.append(f"""
   procedure Handler_{i} (Self : in out Instance; Arg : in Natural) is
      Result : Natural := 0;
   begin
      for J in 1 .. Arg loop
         Result := Result + J * {i};
      end loop;
      Self.Set_Value (Result);
   end Handler_{i};
""")
    return f"""package body Large_Component.Implementation is
{"".join(procedures)}
end Large_Component.Implementation;
"""


@pytest.fixture
def sample_yaml():
    """Small YAML model file."""
    return """---
description: This component echoes CCSDS packets.
execution: passive
connectors:
  - description: The CCSDS receive connector.
    type: Ccsds_Space_Packet.T
    kind: recv_sync
  - description: The packet send connector.
    type: Packet.T
    kind: send
"""


@pytest.fixture
def sample_chunk():
    """A single Chunk object for testing."""
    return Chunk(
        id="abc123",
        text="package Foo is\n   type Bar is record\n      X : Integer;\n   end record;\nend Foo;",
        file_path="adamant/src/types/foo/foo.ads",
        start_line=1,
        end_line=5,
        chunk_type="spec",
        component_name="foo",
        package_name="Foo",
        language="ada",
        codebase="adamant",
    )


@pytest.fixture
def sample_chunks():
    """Multiple chunks for batch testing."""
    return [
        Chunk(
            id=f"chunk_{i}",
            text=f"-- Chunk {i}\npackage Chunk_{i} is\nend Chunk_{i};",
            file_path=f"adamant/src/types/chunk_{i}/chunk_{i}.ads",
            start_line=1,
            end_line=3,
            chunk_type="spec",
            component_name=f"chunk_{i}",
            package_name=f"Chunk_{i}",
            language="ada",
            codebase="adamant",
        )
        for i in range(5)
    ]


@pytest.fixture
def mock_openai_embeddings():
    """Mock OpenAI embeddings returning deterministic 1536-dim vectors."""
    with patch("src.ingestion.embedder.OpenAIEmbeddings") as mock_cls:
        instance = MagicMock()
        instance.embed_documents.return_value = [[0.1] * 1536]
        instance.embed_query.return_value = [0.1] * 1536
        mock_cls.return_value = instance
        yield instance
