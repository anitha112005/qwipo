const express = require('express');
const Product = require('../models/Product');
const User = require('../models/User');
const mlService = require('../services/mlService');
const behaviorMLService = require('../services/behaviorMLService');
const simpleOrderRecommendationService = require('../services/simpleOrderRecommendationService');
const { protect } = require('../middleware/auth');
const logger = require('../utils/logger');

const router = express.Router();

// @desc    Get personalized recommendations for user
// @route   GET /api/recommendations
// @access  Public
router.get('/', async (req, res) => {
  try {
    const { limit = 10, type = 'hybrid' } = req.query;
    // For public access, use a default user ID or get random products
    const userId = req.user?._id.toString() || 'default-user';

    let recommendations = [];

    // If no user is authenticated, return popular products
    if (!req.user) {
      const popularProducts = await Product.find({ isActive: true })
        .sort({ 'ratings.count': -1, 'ratings.average': -1 })
        .limit(parseInt(limit))
        .lean();
      
      return res.json({
        success: true,
        data: {
          recommendations: popularProducts.map(product => ({
            productId: product._id,
            score: product.ratings.average || 4.0,
            reason: 'Popular product',
            product: {
              _id: product._id,
              name: product.name,
              brand: product.brand,
              category: product.category,
              businessType: product.businessType,
              price: product.price,
              images: product.images,
              ratings: product.ratings,
              inventory: product.inventory || { stock: 100 }, // Add default inventory
              description: product.description
            }
          }))
        }
      });
    }

    // Get user's business type for filtering
    const user = await User.findById(req.user._id);
    const userBusinessType = user?.businessType;

    switch (type) {
      case 'order-based':
        // Use the new order-based recommendation system
        const orderBasedRecs = await simpleOrderRecommendationService.getOrderBasedRecommendations(userId, parseInt(limit));
        return res.json({
          success: true,
          data: {
            recommendations: orderBasedRecs.map(rec => ({
              productId: rec.product._id,
              score: rec.score,
              matchPercentage: rec.matchPercentage,
              reason: rec.reason,
              type: rec.type,
              product: rec.product
            }))
          }
        });
      case 'collaborative':
        recommendations = await behaviorMLService.getAdvancedCollaborativeRecommendations(userId, parseInt(limit));
        break;
      case 'content':
        recommendations = await behaviorMLService.getBehaviorBasedContentRecommendations(userId, parseInt(limit));
        break;
      case 'trending':
        recommendations = await behaviorMLService.getPersonalizedTrendingRecommendations(userId, parseInt(limit));
        break;
      case 'search-based':
        recommendations = await behaviorMLService.getSearchPatternRecommendations(userId, parseInt(limit));
        break;
      case 'hybrid':
      default:
        // Try order-based recommendations first for authenticated users
        if (req.user) {
          const orderBasedRecs = await simpleOrderRecommendationService.getOrderBasedRecommendations(userId, parseInt(limit));
          if (orderBasedRecs && orderBasedRecs.length > 0) {
            return res.json({
              success: true,
              data: {
                recommendations: orderBasedRecs.map(rec => ({
                  productId: rec.product._id,
                  score: rec.score,
                  matchPercentage: rec.matchPercentage,
                  reason: rec.reason,
                  type: rec.type,
                  product: rec.product
                }))
              }
            });
          }
        }
        // Fall back to behavioral ML service
        await behaviorMLService.initialize();
        recommendations = await behaviorMLService.getComprehensiveRecommendations(userId, parseInt(limit));
        break;
    }

    if (recommendations.length === 0) {
      // Fallback to trending for new users
      await behaviorMLService.initialize();
      recommendations = await behaviorMLService.getTrendingRecommendations(parseInt(limit));
    }

    // Extract product IDs for database query
    const productIds = recommendations.map(rec => rec.productId);

    // Get product details - filter by user's business type
    const productQuery = {
      _id: { $in: productIds },
      isActive: true
    };
    
    // Filter by business type if user has one
    if (userBusinessType) {
      productQuery.businessType = userBusinessType;
    }
    
    const products = await Product.find(productQuery).lean();

    // If no products match business type, get fallback products
    if (products.length === 0 && userBusinessType) {
      const fallbackProducts = await Product.find({
        isActive: true,
        businessType: userBusinessType
      })
      .sort({ 'ratings.count': -1, 'ratings.average': -1 })
      .limit(parseInt(limit))
      .lean();
      
      return res.json({
        success: true,
        data: {
          recommendations: fallbackProducts.map(product => ({
            productId: product._id,
            score: product.ratings.average || 4.0,
            reason: `Popular ${userBusinessType} product`,
            product: {
              _id: product._id,
              name: product.name,
              brand: product.brand,
              category: product.category,
              businessType: product.businessType,
              price: product.price,
              images: product.images,
              ratings: product.ratings,
              inventory: product.inventory || { stock: 100 },
              description: product.description
            }
          }))
        }
      });
    }

    // Combine recommendations with product details
    const enrichedRecommendations = recommendations.map(rec => {
      const product = products.find(p => p._id.toString() === rec.productId);
      return {
        ...rec,
        product: product ? {
          _id: product._id,
          name: product.name,
          brand: product.brand,
          category: product.category,
          businessType: product.businessType,
          price: product.price,
          images: product.images,
          ratings: product.ratings,
          inventory: product.inventory || { stock: 100 },
          description: product.description
        } : null
      };
    }).filter(rec => rec.product !== null);

    // Track recommendation view (only if user is authenticated)
    if (req.user && userId !== 'default-user') {
      await User.findByIdAndUpdate(userId, {
        $push: {
          recommendations: {
            products: productIds,
            reason: `${type} recommendation`,
            score: recommendations[0]?.score || 0,
            createdAt: new Date()
          }
        }
      });
    }

    res.json({
      success: true,
      data: {
        recommendations: enrichedRecommendations,
        type,
        total: enrichedRecommendations.length
      }
    });
  } catch (error) {
    logger.error('Get recommendations error:', error);
    res.status(500).json({
      success: false,
      message: 'Error fetching recommendations'
    });
  }
});

// @desc    Get category-based recommendations
// @route   GET /api/recommendations/category/:category
// @access  Private
router.get('/category/:category', protect, async (req, res) => {
  try {
    const { category } = req.params;
    const { limit = 10 } = req.query;
    const userId = req.user._id.toString();

    // Get user preferences for this category
    const user = await User.findById(userId).lean();
    const userProfile = user.preferences || {};

    // Find products in category
    let products = await Product.find({
      category: new RegExp(category, 'i'),
      isActive: true,
      'inventory.stock': { $gt: 0 }
    }).lean();

    // Score products based on user preferences
    products = products.map(product => {
      let score = 0;

      // Brand preference
      if (userProfile.brands && userProfile.brands.includes(product.brand)) {
        score += 0.5;
      }

      // Price preference
      if (userProfile.priceRange) {
        const priceRatio = Math.abs(product.price.discountedPrice - userProfile.priceRange.max) / userProfile.priceRange.max;
        score += Math.max(0, 1 - priceRatio) * 0.3;
      }

      // Popularity score
      score += Math.log(1 + (product.analytics?.purchases || 0)) * 0.2;

      return { ...product, recommendationScore: score };
    });

    // Sort by score and limit
    products.sort((a, b) => b.recommendationScore - a.recommendationScore);
    products = products.slice(0, parseInt(limit));

    res.json({
      success: true,
      data: {
        category,
        products,
        total: products.length
      }
    });
  } catch (error) {
    logger.error('Category recommendations error:', error);
    res.status(500).json({
      success: false,
      message: 'Error fetching category recommendations'
    });
  }
});

// @desc    Get similar products
// @route   GET /api/recommendations/similar/:productId
// @access  Private
router.get('/similar/:productId', protect, async (req, res) => {
  try {
    const { productId } = req.params;
    const { limit = 5 } = req.query;

    const baseProduct = await Product.findById(productId).lean();
    if (!baseProduct) {
      return res.status(404).json({
        success: false,
        message: 'Product not found'
      });
    }

    // Find similar products based on category and brand
    const similarProducts = await Product.find({
      _id: { $ne: productId },
      $or: [
        { category: baseProduct.category },
        { brand: baseProduct.brand },
        { tags: { $in: baseProduct.tags || [] } }
      ],
      isActive: true,
      'inventory.stock': { $gt: 0 }
    })
    .limit(parseInt(limit))
    .lean();

    res.json({
      success: true,
      data: {
        baseProduct: {
          _id: baseProduct._id,
          name: baseProduct.name,
          brand: baseProduct.brand,
          category: baseProduct.category
        },
        similarProducts
      }
    });
  } catch (error) {
    logger.error('Similar products error:', error);
    res.status(500).json({
      success: false,
      message: 'Error fetching similar products'
    });
  }
});

// @desc    Track recommendation interaction
// @route   POST /api/recommendations/track
// @access  Private
router.post('/track', protect, async (req, res) => {
  try {
    const { productId, action, recommendationId } = req.body;
    const userId = req.user._id.toString();

    if (!productId || !action) {
      return res.status(400).json({
        success: false,
        message: 'Product ID and action are required'
      });
    }

    // Update recommendation tracking
    if (recommendationId) {
      await User.updateOne(
        { 
          _id: userId,
          'recommendations._id': recommendationId
        },
        {
          $set: {
            [`recommendations.$.${action}`]: true,
            'recommendations.$.updatedAt': new Date()
          }
        }
      );
    }

    // Track product interaction
    const updateData = {};
    switch (action) {
      case 'clicked':
        updateData['analytics.views'] = 1;
        break;
      case 'purchased':
        updateData['analytics.purchases'] = 1;
        updateData['analytics.lastPurchased'] = new Date();
        break;
    }

    if (Object.keys(updateData).length > 0) {
      await Product.updateOne({ _id: productId }, { $inc: updateData });
    }

    // Send real-time notification via socket
    const io = req.app.get('io');
    if (io) {
      io.to(userId).emit('recommendation-interaction', {
        productId,
        action,
        timestamp: new Date()
      });
    }

    res.json({
      success: true,
      message: 'Interaction tracked successfully'
    });
  } catch (error) {
    logger.error('Track recommendation error:', error);
    res.status(500).json({
      success: false,
      message: 'Error tracking interaction'
    });
  }
});

// @desc    Get recommendation analytics
// @route   GET /api/recommendations/analytics
// @access  Private
router.get('/analytics', protect, async (req, res) => {
  try {
    const userId = req.user._id.toString();

    const user = await User.findById(userId)
      .populate('recommendations.products', 'name brand category price')
      .lean();

    if (!user || !user.recommendations) {
      return res.json({
        success: true,
        data: {
          totalRecommendations: 0,
          clickedRecommendations: 0,
          purchasedRecommendations: 0,
          clickThroughRate: 0,
          conversionRate: 0,
          recentRecommendations: []
        }
      });
    }

    const recommendations = user.recommendations;
    const totalRecommendations = recommendations.length;
    const clickedRecommendations = recommendations.filter(r => r.clicked).length;
    const purchasedRecommendations = recommendations.filter(r => r.purchased).length;

    const analytics = {
      totalRecommendations,
      clickedRecommendations,
      purchasedRecommendations,
      clickThroughRate: totalRecommendations > 0 ? (clickedRecommendations / totalRecommendations * 100).toFixed(2) : 0,
      conversionRate: totalRecommendations > 0 ? (purchasedRecommendations / totalRecommendations * 100).toFixed(2) : 0,
      recentRecommendations: recommendations
        .sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt))
        .slice(0, 10)
    };

    res.json({
      success: true,
      data: analytics
    });
  } catch (error) {
    logger.error('Recommendation analytics error:', error);
    res.status(500).json({
      success: false,
      message: 'Error fetching analytics'
    });
  }
});

// @desc    Refresh recommendations (retrain model)
// @route   POST /api/recommendations/refresh
// @access  Private
router.post('/refresh', protect, async (req, res) => {
  try {
    // Trigger ML model update
    await mlService.updateModel();

    res.json({
      success: true,
      message: 'Recommendations refreshed successfully',
      data: mlService.getModelStatus()
    });
  } catch (error) {
    logger.error('Refresh recommendations error:', error);
    res.status(500).json({
      success: false,
      message: 'Error refreshing recommendations'
    });
  }
});

// @desc    Update ML model with user interaction (real-time learning)
// @route   POST /api/recommendations/interaction
// @access  Public
router.post('/interaction', async (req, res) => {
  try {
    const { userId, productId, interactionType, weight } = req.body;
    
    if (!userId || !productId || !interactionType) {
      return res.status(400).json({
        success: false,
        message: 'userId, productId, and interactionType are required'
      });
    }

    // Update ML model with interaction
    await mlService.updateWithInteraction(
      userId, 
      productId, 
      interactionType, 
      weight || 1.0
    );

    res.json({
      success: true,
      message: 'Interaction recorded successfully',
      data: {
        userId,
        productId,
        interactionType,
        weight: weight || 1.0
      }
    });
  } catch (error) {
    logger.error('Record interaction error:', error);
    res.status(500).json({
      success: false,
      message: 'Failed to record interaction'
    });
  }
});

// @desc    Get ML model status and statistics
// @route   GET /api/recommendations/model-status
// @access  Public
router.get('/model-status', async (req, res) => {
  try {
    const status = mlService.getModelStatus();
    
    res.json({
      success: true,
      data: {
        modelStatus: status,
        algorithms: {
          collaborative: 'Enhanced cosine similarity-based filtering',
          content: 'Advanced TF-IDF with KNN',
          clustering: 'K-means user segmentation',
          hybrid: 'Multi-algorithm ensemble with business logic',
          realTimeLearning: 'Continuous model updates'
        },
        availableTypes: ['collaborative', 'content', 'trending', 'cluster', 'hybrid']
      }
    });
  } catch (error) {
    logger.error('Get model status error:', error);
    res.status(500).json({
      success: false,
      message: 'Failed to get model status'
    });
  }
});

module.exports = router;
