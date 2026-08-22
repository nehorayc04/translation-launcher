using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Runtime.CompilerServices;
using System.Text;
using FMT.FileTools;
using FMT.Logging;
using FMT.Models.Assets.AssetEntry.Entries;
using FMT.PluginInterfaces;
using FMT.PluginInterfaces.Assets;
using FMT.ProfileSystem;
using FMT.ServicesManagers;
using FMT.ServicesManagers.AssetEntryServicing;
using FMT.ServicesManagers.Interfaces;

namespace BF6Plugin.Cache;

public class BF6CacheReader : ICacheReader
{
	[field: CompilerGenerated]
	[field: DebuggerBrowsable(/*Could not decode attribute arguments.*/)]
	protected ILogger Logger
	{
		[CompilerGenerated]
		get;
		[CompilerGenerated]
		set;
	}

	public ulong EbxDataOffset
	{
		get
		{
			//IL_0000: Unknown result type (might be due to invalid IL or missing references)
			throw new NotImplementedException();
		}
		set
		{
			//IL_0000: Unknown result type (might be due to invalid IL or missing references)
			throw new NotImplementedException();
		}
	}

	public ulong ResDataOffset
	{
		get
		{
			//IL_0000: Unknown result type (might be due to invalid IL or missing references)
			throw new NotImplementedException();
		}
		set
		{
			//IL_0000: Unknown result type (might be due to invalid IL or missing references)
			throw new NotImplementedException();
		}
	}

	public ulong ChunkDataOffset
	{
		get
		{
			//IL_0000: Unknown result type (might be due to invalid IL or missing references)
			throw new NotImplementedException();
		}
		set
		{
			//IL_0000: Unknown result type (might be due to invalid IL or missing references)
			throw new NotImplementedException();
		}
	}

	public ulong NameToPositionOffset
	{
		get
		{
			//IL_0000: Unknown result type (might be due to invalid IL or missing references)
			throw new NotImplementedException();
		}
		set
		{
			//IL_0000: Unknown result type (might be due to invalid IL or missing references)
			throw new NotImplementedException();
		}
	}

	[field: CompilerGenerated]
	[field: DebuggerBrowsable(/*Could not decode attribute arguments.*/)]
	private Dictionary<ulong, string> VFSFolders
	{
		[CompilerGenerated]
		get;
	} = new Dictionary<ulong, string>();

	[field: CompilerGenerated]
	[field: DebuggerBrowsable(/*Could not decode attribute arguments.*/)]
	private int? FileVersion
	{
		[CompilerGenerated]
		get;
		[CompilerGenerated]
		set;
	}

	public bool Read(ILogger logger)
	{
		//IL_004f: Unknown result type (might be due to invalid IL or missing references)
		//IL_0059: Expected O, but got Unknown
		//IL_0054: Unknown result type (might be due to invalid IL or missing references)
		//IL_005b: Expected O, but got Unknown
		Logger = logger;
		IFileSystemService instance = SingletonService.GetInstance<IFileSystemService>();
		IAssetManagementService instance2 = SingletonService.GetInstance<IAssetManagementService>();
		BF6CacheHelpers bF6CacheHelpers = new BF6CacheHelpers();
		SingletonService.GetInstance<IFileSystemService>().TOCFileType = typeof(BF6TOCFile);
		if (!File.Exists(bF6CacheHelpers.GetCachePath()))
		{
			return false;
		}
		NativeReader val = new NativeReader((Stream)new FileStream(bF6CacheHelpers.GetCachePath(), (FileMode)3, (FileAccess)1));
		try
		{
			FileVersion = ((BinaryReader)val).ReadInt32();
			int? fileVersion = FileVersion;
			int? num = fileVersion;
			return ReadCacheV1(logger);
		}
		finally
		{
			((global::System.IDisposable)val)?.Dispose();
		}
	}

	public bool ReadCacheV1(ILogger logger)
	{
		//IL_0041: Unknown result type (might be due to invalid IL or missing references)
		//IL_004b: Expected O, but got Unknown
		//IL_0046: Unknown result type (might be due to invalid IL or missing references)
		//IL_004d: Expected O, but got Unknown
		//IL_0124: Unknown result type (might be due to invalid IL or missing references)
		//IL_012b: Expected O, but got Unknown
		//IL_0159: Unknown result type (might be due to invalid IL or missing references)
		//IL_0163: Expected O, but got Unknown
		//IL_015e: Unknown result type (might be due to invalid IL or missing references)
		//IL_0165: Expected O, but got Unknown
		//IL_0200: Unknown result type (might be due to invalid IL or missing references)
		//IL_0207: Expected O, but got Unknown
		Logger = logger;
		IFileSystemService instance = SingletonService.GetInstance<IFileSystemService>();
		IAssetManagementService instance2 = SingletonService.GetInstance<IAssetManagementService>();
		BF6CacheHelpers bF6CacheHelpers = new BF6CacheHelpers();
		if (!File.Exists(bF6CacheHelpers.GetCachePath()))
		{
			return false;
		}
		byte[] array = null;
		NativeReader val = new NativeReader((Stream)new FileStream(bF6CacheHelpers.GetCachePath(), (FileMode)3, (FileAccess)1));
		try
		{
			if (((BinaryReader)val).ReadInt32() != bF6CacheHelpers.Version)
			{
				return false;
			}
			if (val.ReadLengthPrefixedString() != ProfileManager.Instance.Name)
			{
				return false;
			}
			ulong num = val.ReadULong((Endian)0);
			if (num != bF6CacheHelpers.GetSystemIteration())
			{
				return false;
			}
			long exeWriteTime = bF6CacheHelpers.GetExeWriteTime();
			long num2 = val.ReadLong((Endian)0);
			if (exeWriteTime != num2)
			{
				return false;
			}
			long installWriteTime = bF6CacheHelpers.GetInstallWriteTime();
			long num3 = val.ReadLong((Endian)0);
			if (installWriteTime != num3)
			{
				return false;
			}
			long num4 = val.Length - val.Position;
			MemoryStream val2 = new MemoryStream(((BinaryReader)val).ReadBytes((int)num4));
			try
			{
				array = bF6CacheHelpers.Decompress(val2.ToArray());
			}
			finally
			{
				((global::System.IDisposable)val2)?.Dispose();
			}
		}
		finally
		{
			((global::System.IDisposable)val)?.Dispose();
		}
		NativeReader val3 = new NativeReader((Stream)new MemoryStream(array));
		try
		{
			logger.Log("Cache: Reading bundles", global::System.Array.Empty<object>());
			int num5 = 0;
			num5 = val3.ReadInt((Endian)0);
			for (int i = 0; i < num5; i++)
			{
				if (i % 100 == 0)
				{
					int num6 = (int)Math.Round((double)i / (double)num5 * 100.0);
					logger.LogProgress(num6);
					logger.Log($"Cache: Reading bundles [{num6}%]", global::System.Array.Empty<object>());
				}
				BundleEntry val4 = new BundleEntry();
				ushort num7 = val3.ReadUShort((Endian)0);
				val4.Name = Encoding.UTF8.GetString(((BinaryReader)val3).ReadBytes((int)num7));
				val4.SuperBundleId = val3.ReadInt((Endian)0);
				if (instance2 != null)
				{
					instance2.Bundles.Add(val4);
				}
			}
			logger.Log("Cache: Reading VFS Folders", global::System.Array.Empty<object>());
			num5 = val3.ReadInt((Endian)0);
			for (int j = 0; j < num5; j++)
			{
				if (j % 100 == 0)
				{
					int num8 = (int)Math.Round((double)j / (double)num5 * 100.0);
					logger.LogProgress(num8);
					logger.Log($"Cache: Reading VFS [{num8}%]", global::System.Array.Empty<object>());
				}
				ulong num9 = val3.ReadULong((Endian)0);
				string text = val3.ReadLengthPrefixedString();
				VFSFolders.Add(num9, text);
			}
			logger.Log("Cache: Reading Ebx", global::System.Array.Empty<object>());
			num5 = val3.ReadInt((Endian)0);
			for (int k = 0; k < num5; k++)
			{
				if (k % 100 == 0)
				{
					int num10 = (int)Math.Round((double)k / (double)num5 * 100.0);
					logger.LogProgress(num10);
					logger.Log($"Cache: Reading Ebx [{num10}%]", global::System.Array.Empty<object>());
				}
				IEbxAssetEntry val5 = ReadEbxAssetEntry(val3);
				if (instance2 != null)
				{
					instance2.AddEbx((EbxAssetEntry)(object)((val5 is EbxAssetEntry) ? val5 : null));
				}
			}
			logger.Log("Cache: Reading Resources", global::System.Array.Empty<object>());
			num5 = val3.ReadInt((Endian)0);
			for (int l = 0; l < num5; l++)
			{
				if (l % 100 == 0)
				{
					int num11 = (int)Math.Round((double)l / (double)num5 * 100.0);
					logger.LogProgress(num11);
					logger.Log($"Cache: Reading Resources [{num11}%]", global::System.Array.Empty<object>());
				}
				IResourceAssetEntry val6 = ReadResAssetEntry(val3);
				if (instance2 != null)
				{
					instance2.AddRes((ResAssetEntry)(object)((val6 is ResAssetEntry) ? val6 : null));
				}
			}
			logger.Log("Cache: Reading Chunks", global::System.Array.Empty<object>());
			num5 = val3.ReadInt((Endian)0);
			for (int m = 0; m < num5; m++)
			{
				if (m % 100 == 0)
				{
					int num12 = (int)Math.Round((double)m / (double)num5 * 100.0);
					logger.LogProgress(num12);
					logger.Log($"Cache: Reading Chunks [{num12}%]", global::System.Array.Empty<object>());
				}
				IChunkAssetEntry val7 = ReadChunkAssetEntry(val3);
				if (instance2 != null)
				{
					instance2.AddChunk((ChunkAssetEntry)(object)((val7 is ChunkAssetEntry) ? val7 : null));
				}
			}
			logger.Log("Cache: Reading Chunks in Bundles", global::System.Array.Empty<object>());
			num5 = val3.ReadInt((Endian)0);
			for (int n = 0; n < num5; n++)
			{
				if (n % 100 == 0)
				{
					int num13 = (int)Math.Round((double)n / (double)num5 * 100.0);
					logger.LogProgress(num13);
					logger.Log($"Cache: Reading Chunks [{num13}%]", global::System.Array.Empty<object>());
				}
				IChunkAssetEntry val8 = ReadChunkAssetEntry(val3);
				val8.IsTocChunk = true;
				if (instance2 != null)
				{
					instance2.AddChunk((ChunkAssetEntry)(object)((val8 is ChunkAssetEntry) ? val8 : null));
				}
			}
		}
		finally
		{
			((global::System.IDisposable)val3)?.Dispose();
		}
		array = null;
		VFSFolders.Clear();
		GC.Collect(GC.MaxGeneration, (GCCollectionMode)1, true, true);
		return true;
	}

	public virtual IEbxAssetEntry ReadEbxAssetEntry(NativeReader nativeReader)
	{
		IAssetEntry obj = SingletonService.GetInstance<IAssetEntryServiceCollectionProvider>().GetAssetEntryServiceForAssetEntry(typeof(EbxAssetEntry)).ReadAssetEntryInfo(nativeReader.ReadLengthPrefixedBytes());
		return (IEbxAssetEntry)(object)((obj is EbxAssetEntry) ? obj : null);
	}

	public virtual IResourceAssetEntry ReadResAssetEntry(NativeReader nativeReader)
	{
		IAssetEntry obj = SingletonService.GetInstance<IAssetEntryServiceCollectionProvider>().GetAssetEntryServiceForAssetEntry(typeof(ResAssetEntry)).ReadAssetEntryInfo(nativeReader.ReadLengthPrefixedBytes());
		return (IResourceAssetEntry)(object)((obj is ResAssetEntry) ? obj : null);
	}

	public virtual IChunkAssetEntry ReadChunkAssetEntry(NativeReader nativeReader)
	{
		IAssetEntry obj = SingletonService.GetInstance<IAssetEntryServiceCollectionProvider>().GetAssetEntryServiceForAssetEntry(typeof(ChunkAssetEntry)).ReadAssetEntryInfo(nativeReader.ReadLengthPrefixedBytes());
		return (IChunkAssetEntry)(object)((obj is ChunkAssetEntry) ? obj : null);
	}

	public bool DoesCacheNeedRebuilding(ILogger logger)
	{
		//IL_0028: Unknown result type (might be due to invalid IL or missing references)
		//IL_0032: Expected O, but got Unknown
		//IL_002d: Unknown result type (might be due to invalid IL or missing references)
		//IL_0033: Expected O, but got Unknown
		BF6CacheHelpers bF6CacheHelpers = new BF6CacheHelpers();
		if (!File.Exists(bF6CacheHelpers.GetCachePath()))
		{
			return true;
		}
		NativeReader val = new NativeReader((Stream)new FileStream(bF6CacheHelpers.GetCachePath(), (FileMode)3, (FileAccess)1));
		try
		{
			if (((BinaryReader)val).ReadInt32() != bF6CacheHelpers.Version)
			{
				return true;
			}
			if (val.ReadLengthPrefixedString() != ProfileManager.Instance.Name)
			{
				return true;
			}
			ulong num = val.ReadULong((Endian)0);
			if (num != bF6CacheHelpers.GetSystemIteration())
			{
				return true;
			}
			long exeWriteTime = bF6CacheHelpers.GetExeWriteTime();
			long num2 = val.ReadLong((Endian)0);
			if (exeWriteTime != num2)
			{
				return true;
			}
			long installWriteTime = bF6CacheHelpers.GetInstallWriteTime();
			long num3 = val.ReadLong((Endian)0);
			if (installWriteTime != num3)
			{
				return true;
			}
		}
		finally
		{
			((global::System.IDisposable)val)?.Dispose();
		}
		return false;
	}

	public bool ReadIntoLists(ILogger logger, out List<IEbxAssetEntry> ebxAssetEntries, out List<IResourceAssetEntry> resourceAssetEntries, out List<IChunkAssetEntry> chunkAssetEntries)
	{
		//IL_0094: Unknown result type (might be due to invalid IL or missing references)
		//IL_009e: Expected O, but got Unknown
		//IL_0099: Unknown result type (might be due to invalid IL or missing references)
		//IL_00a0: Expected O, but got Unknown
		//IL_00ea: Unknown result type (might be due to invalid IL or missing references)
		//IL_00f1: Expected O, but got Unknown
		//IL_0058: Unknown result type (might be due to invalid IL or missing references)
		//IL_0062: Expected O, but got Unknown
		//IL_005d: Unknown result type (might be due to invalid IL or missing references)
		//IL_0064: Expected O, but got Unknown
		//IL_011f: Unknown result type (might be due to invalid IL or missing references)
		//IL_0129: Expected O, but got Unknown
		//IL_0124: Unknown result type (might be due to invalid IL or missing references)
		//IL_012b: Expected O, but got Unknown
		//IL_013f: Unknown result type (might be due to invalid IL or missing references)
		//IL_0146: Expected O, but got Unknown
		BF6CacheHelpers bF6CacheHelpers = new BF6CacheHelpers();
		ebxAssetEntries = new List<IEbxAssetEntry>();
		resourceAssetEntries = new List<IResourceAssetEntry>();
		chunkAssetEntries = new List<IChunkAssetEntry>();
		if (!FileVersion.HasValue)
		{
			if (!File.Exists(bF6CacheHelpers.GetCachePath()))
			{
				return false;
			}
			NativeReader val = new NativeReader((Stream)new FileStream(bF6CacheHelpers.GetCachePath(), (FileMode)3, (FileAccess)1, (FileShare)1));
			try
			{
				FileVersion = ((BinaryReader)val).ReadInt32();
			}
			finally
			{
				((global::System.IDisposable)val)?.Dispose();
			}
		}
		byte[] array = null;
		NativeReader val2 = new NativeReader((Stream)new FileStream(bF6CacheHelpers.GetCachePath(), (FileMode)3, (FileAccess)1, (FileShare)1));
		try
		{
			((BinaryReader)val2).ReadInt32();
			val2.ReadLengthPrefixedString();
			ulong num = val2.ReadULong((Endian)0);
			long num2 = val2.ReadLong((Endian)0);
			long num3 = val2.ReadLong((Endian)0);
			long num4 = val2.Length - val2.Position;
			MemoryStream val3 = new MemoryStream(((BinaryReader)val2).ReadBytes((int)num4));
			try
			{
				array = bF6CacheHelpers.Decompress(val3.ToArray());
			}
			finally
			{
				((global::System.IDisposable)val3)?.Dispose();
			}
		}
		finally
		{
			((global::System.IDisposable)val2)?.Dispose();
		}
		NativeReader val4 = new NativeReader((Stream)new MemoryStream(array));
		try
		{
			int num5 = 0;
			num5 = val4.ReadInt((Endian)0);
			for (int i = 0; i < num5; i++)
			{
				BundleEntry val5 = new BundleEntry();
				ushort num6 = val4.ReadUShort((Endian)0);
				((BinaryReader)val4).ReadBytes((int)num6);
				val5.SuperBundleId = val4.ReadInt((Endian)0);
			}
			num5 = val4.ReadInt((Endian)0);
			for (int j = 0; j < num5; j++)
			{
				ulong num7 = val4.ReadULong((Endian)0);
				string text = val4.ReadLengthPrefixedString();
				if (VFSFolders.ContainsKey(num7))
				{
					VFSFolders[num7] = text;
				}
				else
				{
					VFSFolders.Add(num7, text);
				}
			}
			num5 = val4.ReadInt((Endian)0);
			for (int k = 0; k < num5; k++)
			{
				IEbxAssetEntry val6 = ReadEbxAssetEntry(val4);
				ebxAssetEntries.Add(val6);
			}
			num5 = val4.ReadInt((Endian)0);
			for (int l = 0; l < num5; l++)
			{
				IResourceAssetEntry val7 = ReadResAssetEntry(val4);
				resourceAssetEntries.Add(val7);
			}
			num5 = val4.ReadInt((Endian)0);
			for (int m = 0; m < num5; m++)
			{
				IChunkAssetEntry val8 = ReadChunkAssetEntry(val4);
				chunkAssetEntries.Add(val8);
			}
			num5 = val4.ReadInt((Endian)0);
			for (int n = 0; n < num5; n++)
			{
				IChunkAssetEntry val9 = ReadChunkAssetEntry(val4);
				val9.IsTocChunk = true;
				chunkAssetEntries.Add(val9);
			}
		}
		finally
		{
			((global::System.IDisposable)val4)?.Dispose();
		}
		return Enumerable.Any<IEbxAssetEntry>((global::System.Collections.Generic.IEnumerable<IEbxAssetEntry>)ebxAssetEntries) || Enumerable.Any<IResourceAssetEntry>((global::System.Collections.Generic.IEnumerable<IResourceAssetEntry>)resourceAssetEntries) || Enumerable.Any<IChunkAssetEntry>((global::System.Collections.Generic.IEnumerable<IChunkAssetEntry>)chunkAssetEntries);
	}
}
