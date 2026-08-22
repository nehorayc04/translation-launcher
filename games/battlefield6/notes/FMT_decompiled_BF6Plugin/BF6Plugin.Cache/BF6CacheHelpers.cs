using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Runtime.CompilerServices;
using FMT.Db;
using FMT.FileTools.Readers;
using FMT.ProfileSystem;
using FMT.ServicesManagers;
using FMT.ServicesManagers.Interfaces;

namespace BF6Plugin.Cache;

internal class BF6CacheHelpers
{
	[field: CompilerGenerated]
	[field: DebuggerBrowsable(/*Could not decode attribute arguments.*/)]
	public int Version
	{
		[CompilerGenerated]
		get;
	} = 1;

	public string GetCachePath()
	{
		return Path.Combine(AppContext.BaseDirectory, "_GameCaches", ProfileManager.Instance.CacheName + ".cache");
	}

	public ulong GetSystemIteration()
	{
		//IL_0012: Unknown result type (might be due to invalid IL or missing references)
		//IL_0017: Unknown result type (might be due to invalid IL or missing references)
		//IL_0024: Expected O, but got Unknown
		//IL_006d: Unknown result type (might be due to invalid IL or missing references)
		//IL_007d: Expected O, but got Unknown
		//IL_0078: Unknown result type (might be due to invalid IL or missing references)
		//IL_007f: Expected O, but got Unknown
		IFileSystemService instance = SingletonService.GetInstance<IFileSystemService>();
		List<string> val = Enumerable.ToList<string>((global::System.Collections.Generic.IEnumerable<string>)Directory.GetFiles(instance.BasePath, "*layout.toc", new EnumerationOptions
		{
			RecurseSubdirectories = true
		}));
		val = Enumerable.ToList<string>(Enumerable.Where<string>((global::System.Collections.Generic.IEnumerable<string>)val, (Func<string, bool>)((string x) => !x.Contains("ModData"))));
		string text = instance.ResolvePath("native_data/layout.toc", false, false, "ModData");
		DbObject val2 = null;
		DbReader val3 = new DbReader((Stream)new FileStream(text, (FileMode)3, (FileAccess)1), instance.CreateDeobfuscator());
		try
		{
			val2 = val3.ReadDbObject();
		}
		finally
		{
			((global::System.IDisposable)val3)?.Dispose();
		}
		uint num = 0u;
		uint num2 = 0u;
		num = val2.GetValue<uint>("base", 0u);
		num2 = val2.GetValue<uint>("head", 0u);
		return num + num2;
	}

	public long GetExeWriteTime()
	{
		IFileSystemService instance = SingletonService.GetInstance<IFileSystemService>();
		string text = Path.Combine(instance.BasePath, "BF6.exe");
		if (File.Exists(text))
		{
			return File.GetLastWriteTimeUtc(text).ToFileTimeUtc();
		}
		return 0L;
	}

	public long GetInstallWriteTime()
	{
		IFileSystemService instance = SingletonService.GetInstance<IFileSystemService>();
		string text = Path.Combine(instance.BasePath, "__Installer", "InstallLog.txt");
		if (File.Exists(text))
		{
			return File.GetLastWriteTimeUtc(text).ToFileTimeUtc();
		}
		return 0L;
	}

	public byte[] Compress(byte[] data)
	{
		return data;
	}

	public byte[] Decompress(byte[] data)
	{
		return data;
	}
}
