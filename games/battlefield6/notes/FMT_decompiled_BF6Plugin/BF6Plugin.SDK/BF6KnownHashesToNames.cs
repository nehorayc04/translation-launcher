using System.Collections.Generic;
using FMT.PluginInterfaces.SDK;

namespace BF6Plugin.SDK;

public sealed class BF6KnownHashesToNames : ISDKKnownHashesToNames
{
	public int Priority => 1;

	public Dictionary<uint, string> GetKnownHashesToNames()
	{
		Dictionary<uint, string> obj = new Dictionary<uint, string>();
		obj.Add(3045090926u, "TextureAsset");
		return obj;
	}
}
