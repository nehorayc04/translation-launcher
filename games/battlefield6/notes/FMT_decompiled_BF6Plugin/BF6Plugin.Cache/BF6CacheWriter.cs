using System;
using System.Collections;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Runtime.CompilerServices;
using System.Text;
using FMT.FileTools;
using FMT.Hash;
using FMT.Logging;
using FMT.Models.Assets.AssetEntry.Entries;
using FMT.PluginInterfaces;
using FMT.PluginInterfaces.Assets;
using FMT.ProfileSystem;
using FMT.ServicesManagers;
using FMT.ServicesManagers.AssetEntryServicing;
using FMT.ServicesManagers.Interfaces;

namespace BF6Plugin.Cache;

public class BF6CacheWriter : ICacheWriter
{
	[field: CompilerGenerated]
	[field: DebuggerBrowsable(/*Could not decode attribute arguments.*/)]
	public ILogger Logger
	{
		[CompilerGenerated]
		get;
		[CompilerGenerated]
		private set;
	}

	[field: CompilerGenerated]
	[field: DebuggerBrowsable(/*Could not decode attribute arguments.*/)]
	private Dictionary<string, ulong> VFSFolders
	{
		[CompilerGenerated]
		get;
		[CompilerGenerated]
		set;
	}

	public void Write(ILogger logger)
	{
		//IL_0048: Unknown result type (might be due to invalid IL or missing references)
		//IL_0054: Expected O, but got Unknown
		//IL_004f: Unknown result type (might be due to invalid IL or missing references)
		//IL_0056: Expected O, but got Unknown
		//IL_0082: Unknown result type (might be due to invalid IL or missing references)
		//IL_0087: Unknown result type (might be due to invalid IL or missing references)
		//IL_01f9: Unknown result type (might be due to invalid IL or missing references)
		//IL_01fe: Unknown result type (might be due to invalid IL or missing references)
		//IL_0204: Unknown result type (might be due to invalid IL or missing references)
		//IL_0209: Unknown result type (might be due to invalid IL or missing references)
		//IL_0282: Unknown result type (might be due to invalid IL or missing references)
		//IL_0287: Unknown result type (might be due to invalid IL or missing references)
		//IL_02f2: Unknown result type (might be due to invalid IL or missing references)
		//IL_02f7: Unknown result type (might be due to invalid IL or missing references)
		//IL_035c: Unknown result type (might be due to invalid IL or missing references)
		//IL_0361: Unknown result type (might be due to invalid IL or missing references)
		//IL_03f2: Unknown result type (might be due to invalid IL or missing references)
		//IL_0418: Unknown result type (might be due to invalid IL or missing references)
		//IL_0424: Expected O, but got Unknown
		//IL_041f: Unknown result type (might be due to invalid IL or missing references)
		//IL_0426: Expected O, but got Unknown
		Logger = logger;
		BF6CacheHelpers bF6CacheHelpers = new BF6CacheHelpers();
		IAssetManagementService instance = SingletonService.GetInstance<IAssetManagementService>();
		Directory.CreateDirectory(((FileSystemInfo)Directory.GetParent(bF6CacheHelpers.GetCachePath())).FullName);
		if (File.Exists(bF6CacheHelpers.GetCachePath()))
		{
			File.Delete(bF6CacheHelpers.GetCachePath());
		}
		NativeWriter val = new NativeWriter((Stream)new MemoryStream(), false, false);
		byte[] data;
		try
		{
			logger.Log("Writing Bundles", global::System.Array.Empty<object>());
			((BinaryWriter)val).Write(instance.Bundles.Count);
			Enumerator<BundleEntry> enumerator = instance.Bundles.GetEnumerator();
			try
			{
				while (enumerator.MoveNext())
				{
					BundleEntry current = enumerator.Current;
					val.WriteUInt16((ushort)current.Name.Length, (Endian)0);
					val.WriteBytes(Encoding.UTF8.GetBytes(current.Name));
					((BinaryWriter)val).Write(current.SuperBundleId);
				}
			}
			finally
			{
				((global::System.IDisposable)enumerator/*cast due to .constrained prefix*/).Dispose();
			}
			logger.Log("Writing VFS Folders", global::System.Array.Empty<object>());
			VFSFolders = Enumerable.ToDictionary<string, string, ulong>((global::System.Collections.Generic.IEnumerable<string>)Enumerable.OrderBy<string, string>(Enumerable.Distinct<string>(Enumerable.Union<string>(Enumerable.Select<EbxAssetEntry, string>(instance.EnumerateEbx("", false, false, true, ""), (Func<EbxAssetEntry, string>)((EbxAssetEntry x) => ((AssetEntry)x).GetPath() + "/")), Enumerable.Select<ResAssetEntry, string>(instance.EnumerateRes(0u, false, ""), (Func<ResAssetEntry, string>)((ResAssetEntry x) => ((AssetEntry)x).GetPath() + "/")))), (Func<string, string>)((string x) => x)), (Func<string, string>)((string x) => x), (Func<string, ulong>)((string x) => Fnv64.FNV64_String8_Lower(x)));
			((BinaryWriter)val).Write(Enumerable.Count<KeyValuePair<string, ulong>>((global::System.Collections.Generic.IEnumerable<KeyValuePair<string, ulong>>)VFSFolders));
			Enumerator<string, ulong> enumerator2 = VFSFolders.GetEnumerator();
			try
			{
				while (enumerator2.MoveNext())
				{
					KeyValuePair<string, ulong> current2 = enumerator2.Current;
					((BinaryWriter)val).Write(current2.Value);
					val.WriteLengthPrefixedString(current2.Key);
				}
			}
			finally
			{
				((global::System.IDisposable)enumerator2/*cast due to .constrained prefix*/).Dispose();
			}
			logger.Log("Writing Ebx", global::System.Array.Empty<object>());
			List<EbxAssetEntry> val2 = Enumerable.ToList<EbxAssetEntry>(instance.EnumerateEbx("", false, false, true, ""));
			((BinaryWriter)val).Write(Enumerable.Count<EbxAssetEntry>((global::System.Collections.Generic.IEnumerable<EbxAssetEntry>)val2));
			Enumerator<EbxAssetEntry> enumerator3 = val2.GetEnumerator();
			try
			{
				while (enumerator3.MoveNext())
				{
					EbxAssetEntry current3 = enumerator3.Current;
					WriteEbxEntry(val, (IEbxAssetEntry)(object)current3);
				}
			}
			finally
			{
				((global::System.IDisposable)enumerator3/*cast due to .constrained prefix*/).Dispose();
			}
			logger.Log("Writing Res", global::System.Array.Empty<object>());
			List<ResAssetEntry> val3 = Enumerable.ToList<ResAssetEntry>(instance.EnumerateRes(0u, false, ""));
			((BinaryWriter)val).Write(val3.Count);
			Enumerator<ResAssetEntry> enumerator4 = val3.GetEnumerator();
			try
			{
				while (enumerator4.MoveNext())
				{
					ResAssetEntry current4 = enumerator4.Current;
					WriteResEntry(val, (IResourceAssetEntry)(object)current4);
				}
			}
			finally
			{
				((global::System.IDisposable)enumerator4/*cast due to .constrained prefix*/).Dispose();
			}
			logger.Log("Writing Chunks", global::System.Array.Empty<object>());
			List<ChunkAssetEntry> val4 = Enumerable.ToList<ChunkAssetEntry>(instance.EnumerateChunks(false));
			((BinaryWriter)val).Write(val4.Count);
			Enumerator<ChunkAssetEntry> enumerator5 = val4.GetEnumerator();
			try
			{
				while (enumerator5.MoveNext())
				{
					ChunkAssetEntry current5 = enumerator5.Current;
					WriteChunkEntry(val, (IChunkAssetEntry)(object)current5);
				}
			}
			finally
			{
				((global::System.IDisposable)enumerator5/*cast due to .constrained prefix*/).Dispose();
			}
			((BinaryWriter)val).Write(instance.SuperBundleChunks.Count);
			global::System.Collections.Generic.IEnumerator<ChunkAssetEntry> enumerator6 = ((global::System.Collections.Generic.IEnumerable<ChunkAssetEntry>)instance.SuperBundleChunks.Values).GetEnumerator();
			try
			{
				while (((global::System.Collections.IEnumerator)enumerator6).MoveNext())
				{
					ChunkAssetEntry current6 = enumerator6.Current;
					WriteChunkEntry(val, (IChunkAssetEntry)(object)current6);
				}
			}
			finally
			{
				((global::System.IDisposable)enumerator6)?.Dispose();
			}
			data = ((MemoryStream)((BinaryWriter)val).BaseStream).ToArray();
		}
		finally
		{
			((global::System.IDisposable)val)?.Dispose();
		}
		byte[] array = bF6CacheHelpers.Compress(data);
		byte[] array2 = null;
		NativeWriter val5 = new NativeWriter((Stream)new MemoryStream(), false, false);
		try
		{
			((BinaryWriter)val5).Write(bF6CacheHelpers.Version);
			val5.WriteLengthPrefixedString(ProfileManager.Instance.Name);
			((BinaryWriter)val5).Write(bF6CacheHelpers.GetSystemIteration());
			((BinaryWriter)val5).Write(bF6CacheHelpers.GetExeWriteTime());
			((BinaryWriter)val5).Write(bF6CacheHelpers.GetInstallWriteTime());
			((BinaryWriter)val5).Write(array);
			Stream baseStream = ((BinaryWriter)val5).BaseStream;
			array2 = ((MemoryStream)((baseStream is MemoryStream) ? baseStream : null)).ToArray();
		}
		finally
		{
			((global::System.IDisposable)val5)?.Dispose();
		}
		array = null;
		VFSFolders.Clear();
		GC.Collect(GC.MaxGeneration, (GCCollectionMode)1, true, true);
		File.WriteAllBytes(bF6CacheHelpers.GetCachePath(), array2);
		logger.Log("Wrote BF6 cache to " + bF6CacheHelpers.GetCachePath(), global::System.Array.Empty<object>());
	}

	public virtual void WriteEbxEntry(NativeWriter nativeWriter, IEbxAssetEntry ebxEntry)
	{
		nativeWriter.WriteLengthPrefixedBytes(SingletonService.GetInstance<IAssetEntryServiceCollectionProvider>().GetAssetEntryServiceForAssetEntry(typeof(EbxAssetEntry)).WriteAssetEntryInfo((IAssetEntry)(object)ebxEntry));
	}

	public virtual void WriteResEntry(NativeWriter nativeWriter, IResourceAssetEntry resEntry)
	{
		nativeWriter.WriteLengthPrefixedBytes(SingletonService.GetInstance<IAssetEntryServiceCollectionProvider>().GetAssetEntryServiceForAssetEntry(typeof(ResAssetEntry)).WriteAssetEntryInfo((IAssetEntry)(object)resEntry));
	}

	public virtual void WriteChunkEntry(NativeWriter nativeWriter, IChunkAssetEntry chunkEntry)
	{
		nativeWriter.WriteLengthPrefixedBytes(SingletonService.GetInstance<IAssetEntryServiceCollectionProvider>().GetAssetEntryServiceForAssetEntry(typeof(ChunkAssetEntry)).WriteAssetEntryInfo((IAssetEntry)(object)chunkEntry));
	}
}
