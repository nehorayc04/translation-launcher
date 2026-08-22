using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using FMT.Core;
using FMT.Core.Models.TOC;
using FMT.FileTools;
using FMT.Hash;
using FMT.Models.Assets;
using FMT.Models.Assets.AssetEntry.Entries;
using FMT.PluginInterfaces;
using FMT.ServicesManagers;
using FMT.ServicesManagers.Interfaces;

namespace BF6Plugin;

public class BF6TOCFile : TOCFile
{
	private IAssetManagementService assetManagementService => SingletonService.GetInstance<IAssetManagementService>();

	private IFileSystemService fss => SingletonService.GetInstance<IFileSystemService>();

	public BF6TOCFile(string nativeFilePath)
		: base(nativeFilePath)
	{
	}

	public BF6TOCFile(string nativeFilePath, bool log = true, bool process = true, bool modDataPath = false, int sbIndex = -1, bool headerOnly = false)
		: base(nativeFilePath, log, process, modDataPath, sbIndex, headerOnly)
	{
	}

	public BF6TOCFile(Stream tocStream, bool log = true, bool process = true, bool modDataPath = false, int sbIndex = -1, bool headerOnly = false)
		: base(tocStream, log, process, modDataPath, sbIndex, headerOnly)
	{
	}

	protected override ValueTuple<short, byte, bool> FindCatalogCasPatch(NativeReader nativeReader)
	{
		//IL_005a: Unknown result type (might be due to invalid IL or missing references)
		//IL_007e: Unknown result type (might be due to invalid IL or missing references)
		//IL_0083: Unknown result type (might be due to invalid IL or missing references)
		//IL_0074: Unknown result type (might be due to invalid IL or missing references)
		//IL_0087: Unknown result type (might be due to invalid IL or missing references)
		bool flag = Convert.ToBoolean(nativeReader.ReadShort((Endian)1));
		int catalogIndex = nativeReader.ReadInt((Endian)1);
		byte b = Convert.ToByte(nativeReader.ReadShort((Endian)1));
		int num = Enumerable.ToList<Catalog>((global::System.Collections.Generic.IEnumerable<Catalog>)fss.CatalogObjects).FindIndex((Predicate<Catalog>)((Catalog x) => x.PersistentIndex.HasValue && x.PersistentIndex.Value == catalogIndex));
		if (num == -1)
		{
			throw new IndexOutOfRangeException();
		}
		short num2 = (short)num;
		if ((byte)num2 == 255)
		{
			throw new ArithmeticException();
		}
		return new ValueTuple<short, byte, bool>(num2, b, flag);
	}

	public override void ReadChunkData(NativeReader nativeReader)
	{
		//IL_00a2: Unknown result type (might be due to invalid IL or missing references)
		//IL_00a7: Unknown result type (might be due to invalid IL or missing references)
		//IL_00b1: Unknown result type (might be due to invalid IL or missing references)
		//IL_00b3: Unknown result type (might be due to invalid IL or missing references)
		//IL_00cd: Unknown result type (might be due to invalid IL or missing references)
		//IL_010e: Unknown result type (might be due to invalid IL or missing references)
		//IL_0113: Unknown result type (might be due to invalid IL or missing references)
		//IL_0114: Unknown result type (might be due to invalid IL or missing references)
		//IL_0121: Expected O, but got Unknown
		//IL_0206: Unknown result type (might be due to invalid IL or missing references)
		//IL_020b: Unknown result type (might be due to invalid IL or missing references)
		//IL_0215: Unknown result type (might be due to invalid IL or missing references)
		//IL_025b: Unknown result type (might be due to invalid IL or missing references)
		//IL_0260: Unknown result type (might be due to invalid IL or missing references)
		//IL_0274: Unknown result type (might be due to invalid IL or missing references)
		//IL_02b8: Unknown result type (might be due to invalid IL or missing references)
		//IL_02c2: Expected O, but got Unknown
		//IL_02d8: Unknown result type (might be due to invalid IL or missing references)
		//IL_02f2: Unknown result type (might be due to invalid IL or missing references)
		//IL_030b: Unknown result type (might be due to invalid IL or missing references)
		if (((TOCFile)this).MetaData.ChunkCount == 0)
		{
			return;
		}
		nativeReader.Position = 556 + ((TOCFile)this).MetaData.ChunkFlagOffsetPosition;
		for (int i = 0; i < ((TOCFile)this).MetaData.ChunkCount; i++)
		{
			((TOCFile)this).ListTocChunkFlags.Add(nativeReader.ReadInt((Endian)1));
		}
		nativeReader.Position = 556 + ((TOCFile)this).MetaData.ChunkGuidOffset;
		((TOCFile)this).TocChunkGuids = (Guid[])(object)new Guid[((TOCFile)this).MetaData.ChunkCount];
		Dictionary<uint, ChunkAssetEntry> val = new Dictionary<uint, ChunkAssetEntry>();
		ValueTuple<Guid, uint> val3 = default(ValueTuple<Guid, uint>);
		for (int j = 0; j < ((TOCFile)this).MetaData.ChunkCount; j++)
		{
			Guid val2 = nativeReader.ReadGuidReverse();
			((TOCFile)this).TocChunkGuids[j] = val2;
			uint num = nativeReader.ReadUInt((Endian)1);
			uint num2 = num & 0xFFFFFF;
			val3._002Ector(val2, num);
			while (((TOCFile)this).TocChunks.Count <= num2 / 3)
			{
				((TOCFile)this).TocChunks.Add((ChunkAssetEntry)null);
			}
			((TOCFile)this).TocChunks[(int)(num2 / 3)] = new ChunkAssetEntry((IModifiedAssetEntry)null)
			{
				Id = val2
			};
			val.Add(num2, ((TOCFile)this).TocChunks[(int)(num2 / 3)]);
		}
		int num3 = 556 + ((TOCFile)this).MetaData.ChunkGuidOffset + 4 * ((TOCFile)this).MetaData.ChunkCount + 16 * ((TOCFile)this).MetaData.ChunkCount;
		if (nativeReader.Position != num3)
		{
			throw new global::System.Exception("We are not where we expected to be!");
		}
		nativeReader.Position = 556 + ((TOCFile)this).MetaData.ChunkEntryOffset;
		for (int k = 0; k < ((TOCFile)this).MetaData.ChunkCount; k++)
		{
			uint num4 = (uint)(nativeReader.Position - 556 - ((TOCFile)this).MetaData.DataOffset) / 4;
			ChunkAssetEntry val4 = val[num4];
			val4.IsTocChunk = true;
			uint num5 = (uint)nativeReader.Position;
			ValueTuple<short, byte, bool> val5 = ((TOCFile)this).FindCatalogCasPatch(nativeReader);
			((TOCFile)this).TocChunkPatchPositions.Add(((AssetEntry)val4).Id, num5);
			((AssetEntry)val4).SB_CAS_Offset_Position = (int)nativeReader.Position;
			uint num6 = nativeReader.ReadUInt((Endian)1);
			((AssetEntry)val4).SB_CAS_Size_Position = (int)nativeReader.Position;
			uint num7 = nativeReader.ReadUInt((Endian)1);
			((AssetEntry)val4).Sha1 = Sha1.Create(Encoding.ASCII.GetBytes(((object)((AssetEntry)val4).Id/*cast due to .constrained prefix*/).ToString()));
			val4.LogicalOffset = num6;
			((AssetEntry)val4).OriginalSize = (val4.LogicalOffset & 0xFFFF) | num7;
			((AssetEntry)val4).Size = num7;
			((AssetEntry)val4).Location = (AssetDataLocation)3;
			((AssetEntry)val4).ExtraData = (IAssetExtraData)new AssetExtraData();
			((AssetEntry)val4).ExtraData.Unk = 0;
			((AssetEntry)val4).ExtraData.Catalog = (ushort)val5.Item1;
			((AssetEntry)val4).ExtraData.Cas = (ushort)val5.Item2;
			((AssetEntry)val4).ExtraData.IsPatch = val5.Item3;
			((AssetEntry)val4).ExtraData.DataOffset = num6;
			((AssetEntry)val4).Bundles.Add(((TOCFile)this).ChunkDataBundleId);
			if (assetManagementService != null && base.ProcessData)
			{
				assetManagementService.AddChunk(val4);
			}
		}
	}

	public override void ReadCasBundles(NativeReader nativeReader)
	{
		//IL_0096: Unknown result type (might be due to invalid IL or missing references)
		//IL_009d: Expected O, but got Unknown
		//IL_037b: Unknown result type (might be due to invalid IL or missing references)
		//IL_0380: Unknown result type (might be due to invalid IL or missing references)
		//IL_0389: Unknown result type (might be due to invalid IL or missing references)
		//IL_0392: Unknown result type (might be due to invalid IL or missing references)
		//IL_039b: Unknown result type (might be due to invalid IL or missing references)
		//IL_03a4: Unknown result type (might be due to invalid IL or missing references)
		//IL_03ad: Unknown result type (might be due to invalid IL or missing references)
		//IL_03b6: Unknown result type (might be due to invalid IL or missing references)
		//IL_03bf: Unknown result type (might be due to invalid IL or missing references)
		//IL_03cd: Expected O, but got Unknown
		long num = nativeReader.Length - nativeReader.Position;
		if (num == 0 || assetManagementService == null)
		{
			return;
		}
		if (assetManagementService != null && base.DoLogging)
		{
			assetManagementService.Logger.Log("Searching for CAS Data from " + ((TOCFile)this).FileLocation, global::System.Array.Empty<object>());
		}
		for (int i = 0; i < ((TOCFile)this).MetaData.BundleCount; i++)
		{
			nativeReader.Position = ((TOCFile)this).Bundles[i].Offset + 556;
			CASBundle val = new CASBundle();
			if (((TOCFile)this).BundleEntries.Count == 0)
			{
				continue;
			}
			val.BaseBundle = ((TOCFile)this).Bundles[i];
			val.BaseEntry = ((TOCFile)this).BundleEntries[i];
			long position = nativeReader.Position;
			val.unk1 = nativeReader.ReadInt((Endian)1);
			val.unk2 = nativeReader.ReadInt((Endian)1);
			val.FlagsOffset = nativeReader.ReadInt((Endian)1);
			val.EntriesCount = nativeReader.ReadInt((Endian)1);
			val.EntriesOffset = nativeReader.ReadInt((Endian)1);
			val.HeaderSize = nativeReader.ReadInt((Endian)1);
			val.unk4 = nativeReader.ReadInt((Endian)1);
			val.unk5 = nativeReader.ReadInt((Endian)1);
			val.unk6 = nativeReader.ReadInt((Endian)1);
			long position2 = position + val.FlagsOffset;
			nativeReader.Position = position2;
			val.Flags = ((BinaryReader)nativeReader).ReadBytes(val.EntriesCount);
			long position3 = position + val.EntriesOffset;
			nativeReader.Position = position3;
			byte unk = 0;
			bool flag = false;
			byte b = 0;
			byte b2 = 0;
			int catalogIndex = 0;
			for (int j = 0; j < val.EntriesCount; j++)
			{
				if (val.Flags[j] == 128)
				{
					flag = Convert.ToBoolean(nativeReader.ReadShort((Endian)1));
					catalogIndex = nativeReader.ReadInt((Endian)1);
					b2 = Convert.ToByte(nativeReader.ReadShort((Endian)1));
					if (!fss.CatalogsIndexed.ContainsKey(catalogIndex))
					{
						continue;
					}
					Catalog val2 = fss.CatalogsIndexed[catalogIndex];
					int num2 = Enumerable.ToList<Catalog>((global::System.Collections.Generic.IEnumerable<Catalog>)fss.CatalogObjects).FindIndex((Predicate<Catalog>)((Catalog x) => x.PersistentIndex.HasValue && x.PersistentIndex.Value == catalogIndex));
					if (num2 == -1)
					{
						continue;
					}
					b = (byte)num2;
				}
				long position4 = nativeReader.Position;
				uint num3 = nativeReader.ReadUInt((Endian)1);
				long position5 = nativeReader.Position;
				uint num4 = nativeReader.ReadUInt((Endian)1);
				if (j == 0)
				{
					val.Unk = unk;
					val.BundleOffset = num3;
					val.BundleSize = num4;
					val.Cas = b2;
					val.Catalog = b;
					val.Patch = flag;
				}
				else
				{
					val.TOCOffsets.Add(position4);
					val.Offsets.Add(num3);
					val.TOCSizes.Add(position5);
					val.Sizes.Add(num4);
					val.TOCCas.Add((int)b2);
					val.TOCCatalog.Add((int)b);
					val.TOCPatch.Add(flag);
				}
				val.Entries.Add(new CASBundleEntry
				{
					unk = unk,
					isInPatch = flag,
					catalog = b,
					cas = b2,
					bundleSizeInCas = num4,
					locationOfSize = position5,
					bundleOffsetInCas = num3,
					locationOfOffset = position4
				});
			}
			base.CasBundles[i] = val;
		}
	}
}
